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
 * §4.1  SHARED HELPERS FOR DATA HANDLERS
 *
 * Used by every real endpoint below. Conventions (same as routes_gt.c):
 *   - internal linkage for everything (MISRA Rule 8.7)
 *   - single exit per function (Rule 15.5)
 *   - every sqlite3_* / snprintf return value checked or cast to void
 *     (Rule 17.7)
 *
 * Tables (data_2.db):
 *   operator_status(id, line_id, product_name, shift_id, shift_timings,
 *                   operation, operator_roi_name, cam_id, status,
 *                   duration, updated_at)
 *     One row per closed state segment for one operator ROI.
 *     status   = 'ACTIVE' | 'IDLE' | 'AWAY'
 *     duration = seconds (REAL)
 *     updated_at = 'YYYY-MM-DD HH:MM:SS'
 *
 *   product_produced(id, line_id, product_name, shift_id,
 *                    shift_timings, updated_at)
 *     One row per unit produced.
 * ═══════════════════════════════════════════════════════════════════ */

/* Round to a fixed number of decimals without needing <math.h>/-lm.
 * scale = 10.0 -> 1 decimal, 100.0 -> 2 decimals. */
static double round_to(double value, double scale)
{
    double scaled = value * scale;
    long long rounded;

    if (scaled >= 0.0)
    {
        rounded = (long long)(scaled + 0.5);
    }
    else
    {
        rounded = (long long)(scaled - 0.5);
    }
    return (double)rounded / scale;
}

/* Safe percentage: part / whole * 100, 0 when whole is 0. */
static double pct_of(double part, double whole)
{
    double pct = 0.0;

    if (whole > 0.0)
    {
        pct = (part / whole) * 100.0;
    }
    return pct;
}

/* Seconds -> "6h 12m" (or "18m" under an hour), nearest minute. */
static void format_hm(double total_secs, char *out, size_t out_sz)
{
    double secs = (total_secs > 0.0) ? total_secs : 0.0;
    long long total_mins = (long long)((secs / 60.0) + 0.5);
    long long hours = total_mins / 60LL;
    long long mins = total_mins % 60LL;

    if (hours > 0LL)
    {
        (void)snprintf(out, out_sz, "%lldh %lldm", hours, mins);
    }
    else
    {
        (void)snprintf(out, out_sz, "%lldm", mins);
    }
}

/* Runs a single-value SELECT. Returns 1 on success, 0 on SQL error.
 * A NULL result (e.g. MAX() over an empty table) comes back as 0. */
static int32_t db_scalar_int64(sqlite3 *db, const char *sql, long long *out)
{
    sqlite3_stmt *stmt = NULL;
    int32_t ok = 0;

    *out = 0;
    if (sqlite3_prepare_v2(db, sql, -1, &stmt, NULL) == SQLITE_OK)
    {
        if (sqlite3_step(stmt) == SQLITE_ROW)
        {
            if (sqlite3_column_type(stmt, 0) != SQLITE_NULL)
            {
                *out = (long long)sqlite3_column_int64(stmt, 0);
            }
            ok = 1;
        }
    }
    if (ok == 0)
    {
        (void)fprintf(stderr, "[routes] query failed: %s\n  SQL: %s\n",
                      sqlite3_errmsg(db), sql);
    }
    (void)sqlite3_finalize(stmt);
    return ok;
}

static int32_t db_scalar_double(sqlite3 *db, const char *sql, double *out)
{
    sqlite3_stmt *stmt = NULL;
    int32_t ok = 0;

    *out = 0.0;
    if (sqlite3_prepare_v2(db, sql, -1, &stmt, NULL) == SQLITE_OK)
    {
        if (sqlite3_step(stmt) == SQLITE_ROW)
        {
            if (sqlite3_column_type(stmt, 0) != SQLITE_NULL)
            {
                *out = sqlite3_column_double(stmt, 0);
            }
            ok = 1;
        }
    }
    if (ok == 0)
    {
        (void)fprintf(stderr, "[routes] query failed: %s\n  SQL: %s\n",
                      sqlite3_errmsg(db), sql);
    }
    (void)sqlite3_finalize(stmt);
    return ok;
}

/* Serialises a cJSON tree, sends it through send_response() (so it
 * gets the same CORS headers as everything else), and frees both the
 * tree and the printed string. Always consumes `root`. */
static enum MHD_Result send_cjson(struct MHD_Connection *conn,
                                  int status,
                                  cJSON *root)
{
    char *body = NULL;
    enum MHD_Result ret;

    if (root != NULL)
    {
        body = cJSON_PrintUnformatted(root);
    }

    if (body == NULL)
    {
        ret = json_msg(conn, MHD_HTTP_INTERNAL_SERVER_ERROR, "error", "JSON build failed");
    }
    else
    {
        ret = send_response(conn, status, body);
        cJSON_free(body);
    }

    cJSON_Delete(root);
    return ret;
}

/* Adds {"seconds": 3888.0, "display": "1h 5m"} under `key`.
 * Standard shape for any duration value in a response. */
static void json_add_duration(cJSON *root, const char *key, double seconds)
{
    cJSON *obj = cJSON_AddObjectToObject(root, key);
    char display[32];

    if (obj != NULL)
    {
        format_hm(seconds, display, sizeof(display));
        (void)cJSON_AddNumberToObject(obj, "seconds", round_to(seconds, 10.0));
        (void)cJSON_AddStringToObject(obj, "display", display);
    }
}

/* ═══════════════════════════════════════════════════════════════════
 * §4.2  OVERVIEW PAGE
 * ═══════════════════════════════════════════════════════════════════ */

/* ── GET /api/overview/kpi-cards ──────────────────────────────────────
 *
 * The six KPI cards across the top of the Overview page.
 *
 * Total Output     COUNT(*) of product_produced.
 *                  change_pct: 0 for now (no previous-shift comparison yet).
 *
 * Output / Hour    Total Output / hours covered by operator_status,
 *                  where hours = MAX(updated_at) - MIN(updated_at).
 *                  change_pct: 0 for now.
 *
 * Productive Time  SUM(duration) of operator_status rows with
 *                  status = 'ACTIVE'.
 *                  pct = COUNT(ACTIVE rows) / COUNT(all rows) * 100.
 *
 * Idle / Waiting   Same as Productive Time, status = 'IDLE'.
 *
 * Efficiency       value = Productive Time's pct.
 *                  change_pct: 0 for now.
 *
 * SOP Adherence    value 0, change_pct 0 (placeholder).
 *
 * Response:
 * {
 *   "total_output":    { "value": 29,     "change_pct": 0 },
 *   "output_per_hour": { "value": 141.1,  "change_pct": 0 },
 *   "productive_time": { "seconds": 3888.0, "display": "1h 5m",
 *                        "pct_of_available": 39.1 },
 *   "idle_time":       { "seconds": 935.8,  "display": "16m",
 *                        "pct_of_available": 43.5 },
 *   "efficiency":      { "value_pct": 39.1, "change_pct": 0 },
 *   "sop_adherence":   { "value_pct": 0,    "change_pct": 0 }
 * }
 * ─────────────────────────────────────────────────────────────────── */

typedef struct
{
    long long total_rows;
    long long active_rows;
    double active_secs;
    long long idle_rows;
    double idle_secs;
} KpiStatusTotals_t;

/* One pass over operator_status for both the ACTIVE and IDLE cards. */
static int32_t kpi_query_status_totals(sqlite3 *db, KpiStatusTotals_t *t)
{
    static const char *SQL =
        "SELECT COUNT(*), "
        "       COALESCE(SUM(CASE WHEN status = 'ACTIVE' THEN 1 ELSE 0 END), 0), "
        "       COALESCE(SUM(CASE WHEN status = 'ACTIVE' THEN duration ELSE 0.0 END), 0.0), "
        "       COALESCE(SUM(CASE WHEN status = 'IDLE' THEN 1 ELSE 0 END), 0), "
        "       COALESCE(SUM(CASE WHEN status = 'IDLE' THEN duration ELSE 0.0 END), 0.0) "
        "FROM operator_status;";
    sqlite3_stmt *stmt = NULL;
    int32_t ok = 0;

    (void)memset(t, 0, sizeof(*t));
    if (sqlite3_prepare_v2(db, SQL, -1, &stmt, NULL) == SQLITE_OK)
    {
        if (sqlite3_step(stmt) == SQLITE_ROW)
        {
            t->total_rows = (long long)sqlite3_column_int64(stmt, 0);
            t->active_rows = (long long)sqlite3_column_int64(stmt, 1);
            t->active_secs = sqlite3_column_double(stmt, 2);
            t->idle_rows = (long long)sqlite3_column_int64(stmt, 3);
            t->idle_secs = sqlite3_column_double(stmt, 4);
            ok = 1;
        }
    }
    if (ok == 0)
    {
        (void)fprintf(stderr, "[routes] kpi status totals failed: %s\n",
                      sqlite3_errmsg(db));
    }
    (void)sqlite3_finalize(stmt);
    return ok;
}

/* Adds {"value": v, "change_pct": c} under `key`. */
static void kpi_add_value_card(cJSON *root, const char *key,
                               double value, double change_pct)
{
    cJSON *card = cJSON_AddObjectToObject(root, key);

    if (card != NULL)
    {
        (void)cJSON_AddNumberToObject(card, "value", value);
        (void)cJSON_AddNumberToObject(card, "change_pct", change_pct);
    }
}

/* Adds {"value_pct": v, "change_pct": c} under `key`. */
static void kpi_add_pct_card(cJSON *root, const char *key,
                             double value_pct, double change_pct)
{
    cJSON *card = cJSON_AddObjectToObject(root, key);

    if (card != NULL)
    {
        (void)cJSON_AddNumberToObject(card, "value_pct", value_pct);
        (void)cJSON_AddNumberToObject(card, "change_pct", change_pct);
    }
}

/* Adds {"seconds": s, "display": "6h 12m", "pct_of_available": p}. */
static void kpi_add_time_card(cJSON *root, const char *key,
                              double seconds, double pct)
{
    cJSON *card = cJSON_AddObjectToObject(root, key);
    char display[32];

    if (card != NULL)
    {
        format_hm(seconds, display, sizeof(display));
        (void)cJSON_AddNumberToObject(card, "seconds", round_to(seconds, 10.0));
        (void)cJSON_AddStringToObject(card, "display", display);
        (void)cJSON_AddNumberToObject(card, "pct_of_available", round_to(pct, 10.0));
    }
}

static enum MHD_Result handle_overview_kpi_cards(struct MHD_Connection *conn)
{
    sqlite3 *db = db_get_handle();
    enum MHD_Result ret;
    int32_t ok = 0;
    long long total_output = 0;
    double window_hours = 0.0;
    double output_per_hour = 0.0;
    double productive_pct = 0.0;
    double idle_pct = 0.0;
    KpiStatusTotals_t st;
    cJSON *root = NULL;

    (void)memset(&st, 0, sizeof(st));

    if (db == NULL)
    {
        ret = json_msg(conn, MHD_HTTP_INTERNAL_SERVER_ERROR, "error", "DB not open");
    }
    else
    {
        ok = db_scalar_int64(db,
                             "SELECT COUNT(*) FROM product_produced;",
                             &total_output);

        if (ok != 0)
        {
            ok = db_scalar_double(db,
                                  "SELECT (julianday(MAX(updated_at)) - julianday(MIN(updated_at))) * 24.0 "
                                  "FROM operator_status;",
                                  &window_hours);
        }

        if (ok != 0)
        {
            ok = kpi_query_status_totals(db, &st);
        }

        if (ok == 0)
        {
            ret = json_msg(conn, MHD_HTTP_INTERNAL_SERVER_ERROR, "error", "query failed");
        }
        else
        {
            if (window_hours > 0.0)
            {
                output_per_hour = (double)total_output / window_hours;
            }
            productive_pct = pct_of((double)st.active_rows, (double)st.total_rows);
            idle_pct = pct_of((double)st.idle_rows, (double)st.total_rows);

            root = cJSON_CreateObject();
            if (root != NULL)
            {
                kpi_add_value_card(root, "total_output", (double)total_output, 0.0);
                kpi_add_value_card(root, "output_per_hour", round_to(output_per_hour, 10.0), 0.0);
                kpi_add_time_card(root, "productive_time", st.active_secs, productive_pct);
                kpi_add_time_card(root, "idle_time", st.idle_secs, idle_pct);
                kpi_add_pct_card(root, "efficiency", round_to(productive_pct, 10.0), 0.0);
                kpi_add_pct_card(root, "sop_adherence", 0.0, 0.0);
            }
            ret = send_cjson(conn, MHD_HTTP_OK, root);
        }
    }

    return ret;
}

/* ── GET /api/overview/time-distribution ──────────────────────────────
 *
 * Donut chart on the Overview page: total time spent in each status.
 *
 * productive  SUM(duration) of operator_status rows, status = 'ACTIVE'
 * idle        SUM(duration) of operator_status rows, status = 'IDLE'
 * away        SUM(duration) of operator_status rows, status = 'AWAY'
 * total       SUM(duration) of ALL operator_status rows
 *
 * Times only -- the frontend derives the percentages from these.
 *
 * Response:
 * {
 *   "productive": { "seconds": 3888.0, "display": "1h 5m"  },
 *   "idle":       { "seconds": 935.8,  "display": "16m"    },
 *   "away":       { "seconds": 466.5,  "display": "8m"     },
 *   "total":      { "seconds": 5290.3, "display": "1h 28m" }
 * }
 * ─────────────────────────────────────────────────────────────────── */

typedef struct
{
    double active_secs;
    double idle_secs;
    double away_secs;
    double total_secs;
} TimeDistTotals_t;

/* One pass over operator_status for all four totals. */
static int32_t td_query_totals(sqlite3 *db, TimeDistTotals_t *t)
{
    static const char *SQL =
        "SELECT COALESCE(SUM(CASE WHEN status = 'ACTIVE' THEN duration ELSE 0.0 END), 0.0), "
        "       COALESCE(SUM(CASE WHEN status = 'IDLE'   THEN duration ELSE 0.0 END), 0.0), "
        "       COALESCE(SUM(CASE WHEN status = 'AWAY'   THEN duration ELSE 0.0 END), 0.0), "
        "       COALESCE(SUM(duration), 0.0) "
        "FROM operator_status;";
    sqlite3_stmt *stmt = NULL;
    int32_t ok = 0;

    (void)memset(t, 0, sizeof(*t));
    if (sqlite3_prepare_v2(db, SQL, -1, &stmt, NULL) == SQLITE_OK)
    {
        if (sqlite3_step(stmt) == SQLITE_ROW)
        {
            t->active_secs = sqlite3_column_double(stmt, 0);
            t->idle_secs = sqlite3_column_double(stmt, 1);
            t->away_secs = sqlite3_column_double(stmt, 2);
            t->total_secs = sqlite3_column_double(stmt, 3);
            ok = 1;
        }
    }
    if (ok == 0)
    {
        (void)fprintf(stderr, "[routes] time distribution query failed: %s\n",
                      sqlite3_errmsg(db));
    }
    (void)sqlite3_finalize(stmt);
    return ok;
}

static enum MHD_Result handle_overview_time_distribution(struct MHD_Connection *conn)
{
    sqlite3 *db = db_get_handle();
    enum MHD_Result ret;
    TimeDistTotals_t td;
    cJSON *root = NULL;

    (void)memset(&td, 0, sizeof(td));

    if (db == NULL)
    {
        ret = json_msg(conn, MHD_HTTP_INTERNAL_SERVER_ERROR, "error", "DB not open");
    }
    else if (td_query_totals(db, &td) == 0)
    {
        ret = json_msg(conn, MHD_HTTP_INTERNAL_SERVER_ERROR, "error", "query failed");
    }
    else
    {
        root = cJSON_CreateObject();
        if (root != NULL)
        {
            json_add_duration(root, "productive", td.active_secs);
            json_add_duration(root, "idle", td.idle_secs);
            json_add_duration(root, "away", td.away_secs);
            json_add_duration(root, "total", td.total_secs);
        }
        ret = send_cjson(conn, MHD_HTTP_OK, root);
    }

    return ret;
}

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

    /* ── Overview page ───────────────────────────────────────────────── */
    else if (strcmp(url, "/api/overview/kpi-cards") == 0)
    {
        if (strcmp(method, "GET") == 0)
        {
            ret = handle_overview_kpi_cards(connection);
        }
    }
    else if (strcmp(url, "/api/overview/time-distribution") == 0)
    {
        if (strcmp(method, "GET") == 0)
        {
            ret = handle_overview_time_distribution(connection);
        }
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