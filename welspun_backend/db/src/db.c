// ============================================================
// db.c -- SQLite logging layer (see db.h for the schema/contract)
//
// Single-threaded writer: the C++ main loop calls these from one
// thread. WAL journal mode is enabled so a future api.c can read the
// same data.db concurrently without blocking the writer.
//
// SCHEMA CHANGE (this revision): station_timers -> operator_status
// (video_name dropped, several hardcoded + caller-supplied columns
// added); product_produced gains the same hardcoded/caller-supplied
// columns and its product_name is now a fixed constant instead of a
// per-class lookup. See db.h for the full column list.
// ============================================================

#include "db.h"

#include <sqlite3.h>

#include <stdio.h>
#include <string.h>
#include <time.h>

// ------------------------------------------------------------
// Module state
// ------------------------------------------------------------

static sqlite3*      g_db            = NULL;
static sqlite3_stmt* g_stmt_station  = NULL;  // INSERT into operator_status
static sqlite3_stmt* g_stmt_product  = NULL;  // INSERT into product_produced

// ------------------------------------------------------------
// Hardcoded columns, both tables.
//
// These are fixed for the current single-line/single-shift-scheme
// deployment. When there's a real need to vary any of these at
// runtime, turn it into a function parameter (same escape hatch
// VIDEO_NAME used to be) instead of editing call sites everywhere.
// ------------------------------------------------------------

static const char* LINE_ID      = "1";
static const char* PRODUCT_NAME = "ctpat";
static const char* SHIFT_ID     = "1";
static const char* OPERATION    = "hand_towel";   // operator_status only
static const int   CAM_ID       = 1;              // operator_status only

// ------------------------------------------------------------
// Current wall-clock time as an IST "YYYY-MM-DD HH:MM:SS" string.
//
// IST is UTC+05:30 with no daylight saving, so we take UTC and shift
// by a fixed +5h30m. This is independent of the machine's own
// timezone setting -- the box can be on UTC, PST, whatever, and the
// stored timestamp is still correct IST.
// ------------------------------------------------------------

static void ist_now(char* buf, size_t buf_size)
{
    time_t now = time(NULL);
    now += 5 * 3600 + 30 * 60;   // shift UTC -> IST

    struct tm tm_ist;
    gmtime_r(&now, &tm_ist);     // POSIX; gmtime_s on Windows

    strftime(buf, buf_size, "%Y-%m-%d %H:%M:%S", &tm_ist);
}

// ------------------------------------------------------------
// db_init
// ------------------------------------------------------------

int db_init(const char* db_path)
{
    if (g_db)
    {
        return 0;   // already open
    }

    int rc = sqlite3_open(db_path, &g_db);

    if (rc != SQLITE_OK)
    {
        fprintf(stderr, "db: cannot open %s: %s\n",
                db_path, g_db ? sqlite3_errmsg(g_db) : "(no handle)");

        if (g_db)
        {
            sqlite3_close(g_db);
            g_db = NULL;
        }

        return -1;
    }

    // Concurrency-friendly settings for the later read-only API.
    sqlite3_exec(g_db, "PRAGMA journal_mode=WAL;",  NULL, NULL, NULL);
    sqlite3_exec(g_db, "PRAGMA synchronous=NORMAL;", NULL, NULL, NULL);

    // NOTE: CREATE TABLE IF NOT EXISTS only creates tables that don't
    // already exist -- it will NOT rename an old station_timers into
    // operator_status, nor add columns to a data.db left over from
    // before this schema change. Delete/rename the old data.db (or
    // migrate it) before running this version.
    const char* create_sql =
        "CREATE TABLE IF NOT EXISTS operator_status ("
        "  id                INTEGER PRIMARY KEY AUTOINCREMENT,"
        "  line_id           TEXT    NOT NULL,"
        "  product_name      TEXT    NOT NULL,"
        "  shift_id          TEXT    NOT NULL,"
        "  shift_timings     TEXT    NOT NULL,"
        "  operation         TEXT    NOT NULL,"
        "  operator_roi_name TEXT    NOT NULL,"
        "  cam_id            INTEGER NOT NULL,"
        "  status            TEXT    NOT NULL,"
        "  duration          REAL    NOT NULL,"
        "  updated_at        TEXT    NOT NULL"
        ");"
        "CREATE TABLE IF NOT EXISTS product_produced ("
        "  id            INTEGER PRIMARY KEY AUTOINCREMENT,"
        "  line_id       TEXT    NOT NULL,"
        "  product_name  TEXT    NOT NULL,"
        "  shift_id      TEXT    NOT NULL,"
        "  shift_timings TEXT    NOT NULL,"
        "  updated_at    TEXT    NOT NULL"
        ");";

    char* err = NULL;
    rc = sqlite3_exec(g_db, create_sql, NULL, NULL, &err);

    if (rc != SQLITE_OK)
    {
        fprintf(stderr, "db: table creation failed: %s\n", err ? err : "?");
        sqlite3_free(err);
        sqlite3_close(g_db);
        g_db = NULL;
        return -1;
    }

    rc = sqlite3_prepare_v2(
        g_db,
        "INSERT INTO operator_status"
        " (line_id, product_name, shift_id, shift_timings, operation,"
        "  operator_roi_name, cam_id, status, duration, updated_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);",
        -1, &g_stmt_station, NULL);

    if (rc != SQLITE_OK)
    {
        fprintf(stderr, "db: prepare operator_status insert failed: %s\n", sqlite3_errmsg(g_db));
        db_close();
        return -1;
    }

    rc = sqlite3_prepare_v2(
        g_db,
        "INSERT INTO product_produced"
        " (line_id, product_name, shift_id, shift_timings, updated_at)"
        " VALUES (?, ?, ?, ?, ?);",
        -1, &g_stmt_product, NULL);

    if (rc != SQLITE_OK)
    {
        fprintf(stderr, "db: prepare product_produced insert failed: %s\n", sqlite3_errmsg(g_db));
        db_close();
        return -1;
    }

    return 0;
}

// ------------------------------------------------------------
// db_log_station_state
// ------------------------------------------------------------

int db_log_station_state(const char* operator_roi_name,
                         const char* status,
                         double duration_sec,
                         const char* shift_timings)
{
    if (!g_db || !g_stmt_station)
    {
        return -1;   // DB not available -- silent no-op
    }

    char ts[32];
    ist_now(ts, sizeof(ts));

    sqlite3_reset(g_stmt_station);
    sqlite3_clear_bindings(g_stmt_station);

    sqlite3_bind_text  (g_stmt_station, 1, LINE_ID,           -1, SQLITE_STATIC);
    sqlite3_bind_text  (g_stmt_station, 2, PRODUCT_NAME,      -1, SQLITE_STATIC);
    sqlite3_bind_text  (g_stmt_station, 3, SHIFT_ID,          -1, SQLITE_STATIC);
    sqlite3_bind_text  (g_stmt_station, 4, shift_timings,     -1, SQLITE_TRANSIENT);
    sqlite3_bind_text  (g_stmt_station, 5, OPERATION,         -1, SQLITE_STATIC);
    sqlite3_bind_text  (g_stmt_station, 6, operator_roi_name, -1, SQLITE_TRANSIENT);
    sqlite3_bind_int   (g_stmt_station, 7, CAM_ID);
    sqlite3_bind_text  (g_stmt_station, 8, status,            -1, SQLITE_TRANSIENT);
    sqlite3_bind_double(g_stmt_station, 9, duration_sec);
    sqlite3_bind_text  (g_stmt_station, 10, ts,               -1, SQLITE_TRANSIENT);

    int rc = sqlite3_step(g_stmt_station);

    if (rc != SQLITE_DONE)
    {
        fprintf(stderr, "db: operator_status insert failed: %s\n", sqlite3_errmsg(g_db));
        return -1;
    }

    return 0;
}

// ------------------------------------------------------------
// db_log_product
// ------------------------------------------------------------

int db_log_product(const char* shift_timings)
{
    if (!g_db || !g_stmt_product)
    {
        return -1;   // DB not available -- silent no-op
    }

    char ts[32];
    ist_now(ts, sizeof(ts));

    sqlite3_reset(g_stmt_product);
    sqlite3_clear_bindings(g_stmt_product);

    sqlite3_bind_text(g_stmt_product, 1, LINE_ID,       -1, SQLITE_STATIC);
    sqlite3_bind_text(g_stmt_product, 2, PRODUCT_NAME,  -1, SQLITE_STATIC);
    sqlite3_bind_text(g_stmt_product, 3, SHIFT_ID,      -1, SQLITE_STATIC);
    sqlite3_bind_text(g_stmt_product, 4, shift_timings, -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(g_stmt_product, 5, ts,             -1, SQLITE_TRANSIENT);

    int rc = sqlite3_step(g_stmt_product);

    if (rc != SQLITE_DONE)
    {
        fprintf(stderr, "db: product_produced insert failed: %s\n", sqlite3_errmsg(g_db));
        return -1;
    }

    return 0;
}

// ------------------------------------------------------------
// db_close
// ------------------------------------------------------------

void db_close(void)
{
    if (g_stmt_station)
    {
        sqlite3_finalize(g_stmt_station);
        g_stmt_station = NULL;
    }

    if (g_stmt_product)
    {
        sqlite3_finalize(g_stmt_product);
        g_stmt_product = NULL;
    }

    if (g_db)
    {
        sqlite3_close(g_db);
        g_db = NULL;
    }
}

// ------------------------------------------------------------
// db_get_handle -- read-only accessor for the HTTP API layer
// (routes.c). WAL mode (set in db_init) makes this reader + the
// logging writer above safe to run concurrently.
// ------------------------------------------------------------

sqlite3* db_get_handle(void)
{
    return g_db;   // NULL if db_init() was never called / failed
}