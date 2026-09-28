#ifndef DB_H
#define DB_H

/* ============================================================
 * db.h -- SQLite logging layer contract (data.db)
 *
 * SCHEMA CHANGE (this revision):
 *   - station_timers renamed to operator_status. video_name is
 *     dropped. New columns: id (PK), line_id, product_name,
 *     shift_id, shift_timings, operation, operator_roi_name
 *     (was station_name), cam_id -- all ahead of the existing
 *     status/duration/updated_at. line_id/product_name/shift_id/
 *     operation/cam_id are hardcoded constants in db.c; shift_timings
 *     is supplied by the caller per-call (the one field that
 *     actually varies -- from config.json's shift timings).
 *   - product_produced gains id (PK), line_id, product_name,
 *     shift_id, shift_timings ahead of the existing updated_at.
 *     product_name is now the hardcoded "ctpat" constant, not the
 *     detected class name -- db_log_product() no longer takes a
 *     class_id, only the caller-supplied shift_timings.
 *
 * Old data.db files predate this rename/column change -- delete or
 * rename data.db before running this version, or migrate by hand.
 * ============================================================ */

#ifdef __cplusplus
extern "C"
{
#endif

struct sqlite3;

int  db_init(const char *db_path);

void db_close(void);

/* ------------------------------------------------------------
 * db_log_station_state -- CHANGED: now takes shift_timings.
 *
 * operator_roi_name is the station/ROI name (same value the old
 * station_name parameter held). line_id, product_name, shift_id,
 * operation, cam_id are hardcoded in db.c. shift_timings should be
 * the current shift's "HH:MM - HH:MM" string (e.g. ctpat.cpp's
 * getCurrentShiftTimings()); pass "" if unknown.
 * ------------------------------------------------------------ */
int  db_log_station_state(const char *operator_roi_name,
                          const char *status,
                          double duration_sec,
                          const char *shift_timings);

/* ------------------------------------------------------------
 * db_log_product -- CHANGED: no longer takes class_id. product_name
 * is now the hardcoded "ctpat" constant (see db.c), not a per-class
 * lookup. shift_timings is the current shift's "HH:MM - HH:MM"
 * string, same meaning as db_log_station_state's.
 * ------------------------------------------------------------ */
int  db_log_product(const char *shift_timings);

struct sqlite3 *db_get_handle(void);

#ifdef __cplusplus
}
#endif

#endif /* DB_H */