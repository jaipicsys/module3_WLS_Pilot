/*
 * routes.c
 *
 * HTTP API layer for ctpat. This keeps only the INFRASTRUCTURE
 * from the previous project's routes.c:
 *   - request-context pool (accumulates POST/PUT bodies)
 *   - small JSON-building helpers (json_kv_str/int/dbl)
 *   - send_response() / json_msg() (CORS headers, JSON content type)
 *   - the routes_connection_handler() dispatcher shape
 *
 * Everything project-specific from the old file (auth/JWT, cookies,
 * station-monitor/shift-comparison/etc. handlers, the big hand-rolled
 * SQL) has been stripped out on purpose -- your new schema is just
 * station_timers + product_produced (see db.h), so none of that SQL
 * applies. Two example handlers are left in to show the pattern:
 *
 *   GET /api/health           -- no DB access, sanity check
 *   GET /api/units-produced   -- reads product_produced via db_get_handle()
 *
 * Everything else is a TODO stub -- add your own `else if (strcmp(url, ...))`
 * branches in routes_connection_handler() the same way.
 */

#include "routes.h"
#include "db.h"

#include <sqlite3.h>
#include <cjson/cJSON.h>
#include <microhttpd.h>

#include <stdio.h>
#include <string.h>
#include <stdlib.h>

/* ═══════════════════════════════════════════════════════════════════
 * §1  REQUEST CONTEXT  (per-connection accumulator for POST/PUT bodies)
 * ═══════════════════════════════════════════════════════════════════ */

typedef struct
{
    char body[ROUTES_BODY_MAX];
    size_t body_len;
    int completed;
    int responded;
} ReqCtx_t;

#define REQ_CTX_POOL (32U)
static ReqCtx_t s_ctx_pool[REQ_CTX_POOL];
static int32_t s_ctx_used[REQ_CTX_POOL];

static ReqCtx_t *ctx_alloc(void)
{
    uint32_t i;
    ReqCtx_t *ctx = NULL;

    for (i = 0U; i < REQ_CTX_POOL; i++)
    {
        if (s_ctx_used[i] == 0)
        {
            s_ctx_used[i] = 1;
            s_ctx_pool[i].body_len = 0U;
            s_ctx_pool[i].body[0] = '\0';
            s_ctx_pool[i].completed = 0;
            s_ctx_pool[i].responded = 0;
            ctx = &s_ctx_pool[i];
            break;
        }
    }
    return ctx;
}

static void ctx_free(ReqCtx_t *ctx)
{
    uint32_t i;

    if (ctx == NULL)
    {
        return;
    }
    for (i = 0U; i < REQ_CTX_POOL; i++)
    {
        if (&s_ctx_pool[i] == ctx)
        {
            s_ctx_used[i] = 0;
            break;
        }
    }
}

/* ═══════════════════════════════════════════════════════════════════
 * §2  JSON KEY/VALUE HELPERS
 *
 * Small snprintf-based helpers for hand-building a JSON object into
 * a fixed buffer without pulling in cJSON for trivial responses.
 * Use these OR cJSON (already linked, see the example handlers below)
 * -- whichever you find easier per-endpoint.
 * ═══════════════════════════════════════════════════════════════════ */

static void json_kv_str(char *buf, size_t buf_max, size_t *pos,
                        const char *key, const char *val)
{
    int n;

    if ((buf == NULL) || (pos == NULL) || (key == NULL) || (val == NULL))
    {
        return;
    }
    n = snprintf(buf + *pos, buf_max - *pos,
                 (*pos > 1U) ? ",\"%s\":\"%s\"" : "\"%s\":\"%s\"",
                 key, val);
    if (n > 0)
    {
        *pos += (size_t)n;
    }
}

static void json_kv_int(char *buf, size_t buf_max, size_t *pos,
                        const char *key, int32_t val)
{
    int n;

    if ((buf == NULL) || (pos == NULL) || (key == NULL))
    {
        return;
    }
    n = snprintf(buf + *pos, buf_max - *pos,
                 (*pos > 1U) ? ",\"%s\":%d" : "\"%s\":%d",
                 key, (int)val);
    if (n > 0)
    {
        *pos += (size_t)n;
    }
}

static void json_kv_dbl(char *buf, size_t buf_max, size_t *pos,
                        const char *key, double val)
{
    int n;

    if ((buf == NULL) || (pos == NULL) || (key == NULL))
    {
        return;
    }
    n = snprintf(buf + *pos, buf_max - *pos,
                 (*pos > 1U) ? ",\"%s\":%.2f" : "\"%s\":%.2f",
                 key, val);
    if (n > 0)
    {
        *pos += (size_t)n;
    }
}

/* ═══════════════════════════════════════════════════════════════════
 * §3  HTTP SEND HELPERS
 * ═══════════════════════════════════════════════════════════════════ */

static enum MHD_Result send_response(struct MHD_Connection *conn,
                                     int status,
                                     const char *body)
{
    struct MHD_Response *resp;
    enum MHD_Result result;
    const char *origin;

    if (body == NULL)
    {
        body = "{\"error\":\"empty response\"}";
    }

    resp = MHD_create_response_from_buffer(
        strlen(body),
        (void *)body,
        MHD_RESPMEM_MUST_COPY);

    if (resp == NULL)
    {
        return MHD_NO;
    }

    (void)MHD_add_response_header(resp, "Content-Type", "application/json");

    origin = MHD_lookup_connection_value(conn, MHD_HEADER_KIND, "Origin");
    if (origin != NULL)
    {
        (void)MHD_add_response_header(resp, "Access-Control-Allow-Origin", origin);
        (void)MHD_add_response_header(resp, "Vary", "Origin");
    }

    (void)MHD_add_response_header(resp, "Access-Control-Allow-Credentials", "true");
    (void)MHD_add_response_header(resp, "Access-Control-Allow-Headers", "Content-Type, Authorization");
    (void)MHD_add_response_header(resp, "Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS");

    result = MHD_queue_response(conn, (unsigned int)status, resp);
    MHD_destroy_response(resp);
    (void)result;
    return MHD_YES;
}

static enum MHD_Result json_msg(struct MHD_Connection *conn,
                                int status,
                                const char *field,
                                const char *text)
{
    char buf[512U];
    (void)snprintf(buf, sizeof(buf), "{\"%s\":\"%s\"}", field, text);
    return send_response(conn, status, buf);
}

static enum MHD_Result handle_options(struct MHD_Connection *conn)
{
    return send_response(conn, MHD_HTTP_NO_CONTENT, "");
}

/* ═══════════════════════════════════════════════════════════════════
 * §4  EXAMPLE HANDLERS
 *
 * Kept just to show the pattern -- delete or expand as needed.
 * ═══════════════════════════════════════════════════════════════════ */

/* ── GET /api/health ──────────────────────────────────────────────── */
static enum MHD_Result handle_health(struct MHD_Connection *conn)
{
    return json_msg(conn, MHD_HTTP_OK, "status", "ok");
}

/* ── GET /api/units-produced ──────────────────────────────────────── */
/* Total row count in product_produced, i.e. g_units_produced's DB    */
/* mirror. Swap in a time-window WHERE clause (updated_at >= ...) the */
/* same way the old routes.c did once you need "today" / "last 24h".  */
static enum MHD_Result handle_units_produced(struct MHD_Connection *conn)
{
    sqlite3 *raw = db_get_handle();
    sqlite3_stmt *stmt = NULL;
    long long total = 0;

    if (raw == NULL)
    {
        return json_msg(conn, MHD_HTTP_INTERNAL_SERVER_ERROR, "error", "DB not open");
    }

    if (sqlite3_prepare_v2(raw, "SELECT COUNT(*) FROM product_produced;", -1, &stmt, NULL) != SQLITE_OK)
    {
        return json_msg(conn, MHD_HTTP_INTERNAL_SERVER_ERROR, "error", sqlite3_errmsg(raw));
    }

    if (sqlite3_step(stmt) == SQLITE_ROW)
    {
        total = sqlite3_column_int64(stmt, 0);
    }
    sqlite3_finalize(stmt);

    {
        char buf[128U];
        size_t pos = 1U;
        buf[0] = '{';
        json_kv_int(buf, sizeof(buf), &pos, "unitsProduced", (int32_t)total);
        if (pos + 1U < sizeof(buf))
        {
            buf[pos++] = '}';
        }
        buf[pos] = '\0';
        return send_response(conn, MHD_HTTP_OK, buf);
    }
}

/* ─────────────────────────────────────────────────────────────────
 * TODO: add your real endpoints here, e.g.
 *
 *   GET  /api/station-timers?station=<name>&since=<iso>
 *        -> SELECT * FROM station_timers WHERE ...
 *
 *   GET  /api/stations/summary
 *        -> SUM(duration) GROUP BY station_name, status
 *
 * Follow the handle_units_produced() shape above: open db_get_handle(),
 * prepare/bind/step, build JSON (cJSON or the json_kv_* helpers), close
 * the statement, send_response(). (json_kv_dbl is included above and
 * currently unused -- silence the "unused function" warning by using
 * it in your first real handler, or drop it.)
 * ───────────────────────────────────────────────────────────────── */

/* ═══════════════════════════════════════════════════════════════════
 * §5  PUBLIC ENTRY POINTS  (wired into MHD_start_daemon in ctpat.cpp)
 * ═══════════════════════════════════════════════════════════════════ */

void routes_request_completed(
    void *cls,
    struct MHD_Connection *connection,
    void **con_cls,
    enum MHD_RequestTerminationCode toe)
{
    (void)cls;
    (void)connection;
    (void)toe;

    if ((con_cls != NULL) && (*con_cls != NULL))
    {
        ctx_free((ReqCtx_t *)*con_cls);
        *con_cls = NULL;
    }
}

enum MHD_Result routes_connection_handler(
    void *cls,
    struct MHD_Connection *connection,
    const char *url,
    const char *method,
    const char *version,
    const char *upload_data,
    size_t *upload_data_size,
    void **con_cls)
{
    ReqCtx_t *ctx;
    enum MHD_Result ret;

    (void)cls;
    (void)version;

    if (strcmp(method, "OPTIONS") == 0)
        return handle_options(connection);

    if (*con_cls == NULL)
    {
        ctx = ctx_alloc();
        if (ctx == NULL)
        {
            return MHD_NO;
        }
        *con_cls = (void *)ctx;
        return MHD_YES;
    }

    ctx = (ReqCtx_t *)(*con_cls);

    if ((strcmp(method, "POST") == 0) || (strcmp(method, "PUT") == 0))
    {
        if (*upload_data_size > 0U)
        {
            size_t avail = ROUTES_BODY_MAX - ctx->body_len - 1U;
            size_t copy = (*upload_data_size < avail)
                              ? *upload_data_size
                              : avail;
            (void)memcpy(ctx->body + ctx->body_len, upload_data, copy);
            ctx->body_len += copy;
            ctx->body[ctx->body_len] = '\0';
            *upload_data_size = 0U;
            return MHD_YES;
        }
        if (ctx->completed != 0)
        {
            return MHD_YES;
        }
        ctx->completed = 1;
    }

    if (ctx->responded != 0)
    {
        return MHD_YES;
    }

    ret = MHD_NO;

    if (strcmp(url, "/api/health") == 0)
    {
        if (strcmp(method, "GET") == 0)
            ret = handle_health(connection);
    }
    else if (strcmp(url, "/api/units-produced") == 0)
    {
        if (strcmp(method, "GET") == 0)
            ret = handle_units_produced(connection);
    }
    /*
     * TODO: else if (strcmp(url, "/api/your-endpoint") == 0) { ... }
     */
    else
    {
        ret = json_msg(connection, MHD_HTTP_NOT_FOUND, "error", "Not found");
    }

    if (ret == MHD_NO)
        ret = json_msg(connection, MHD_HTTP_METHOD_NOT_ALLOWED, "error", "Method not allowed");

    ctx->responded = 1;
    return ret;
}