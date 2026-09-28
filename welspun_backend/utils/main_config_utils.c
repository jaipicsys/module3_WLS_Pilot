/*
 * main_config_utils.c
 *
 * See main_config_utils.h for the AppConfig shape and config_load()'s
 * contract. This file just reads config.json off disk, parses it
 * with cJSON, and copies/validates fields into an AppConfig.
 *
 * Every field has a documented default (see the DEFAULT_* constants
 * below) EXCEPT the ones that genuinely can't have a safe default:
 * rtsp_url, the three model paths, and the stations array. Those are
 * REQUIRED -- config_load() fails with a specific message if any of
 * them is missing.
 */

#include "main_config_utils.h"

#include <cjson/cJSON.h>

#include <stdio.h>
#include <string.h>
#include <stdlib.h>

/* ------------------------------------------------------------
 * Defaults for every optional field. Keeping these named (rather
 * than magic numbers inline) makes it obvious, reading config_load(),
 * exactly what you get if you leave a given key out of config.json.
 * ------------------------------------------------------------ */

static const bool  DEFAULT_SAVE_OUTPUT_VIDEO   = true;
static const char* DEFAULT_OUTPUT_VIDEO_PATH   = "output_tracking.mp4";
static const char* DEFAULT_FRAME_LOG_PATH      = "frame.txt";
static const char* DEFAULT_DB_PATH             = "data.db";
static const int   DEFAULT_API_PORT            = 5001;

static const int   DEFAULT_PERSON_INPUT_SIZE      = 640;
static const float DEFAULT_PERSON_CONF_THRESHOLD  = 0.50f;
static const float DEFAULT_NMS_THRESHOLD          = 0.45f;
static const int   DEFAULT_PERSON_CLASS_ID        = 0;

static const int   DEFAULT_TOWEL_INPUT_SIZE     = 640;
static const float DEFAULT_TOWEL_CONF_THRESHOLD = 0.50f;
static const int   DEFAULT_TOWEL_CLASS_ID       = 0;

static const int   DEFAULT_POSE_INPUT_SIZE     = 640;
static const float DEFAULT_POSE_CONF_THRESHOLD = 0.50f;

static const float DEFAULT_MIN_TRACK_BOX_AREA           = 100.0f;
static const float DEFAULT_ROI_PERSON_OVERLAP_THRESHOLD = 0.15f;

static const double DEFAULT_TOWEL_LINE_BRIDGE_MAX_GAP_SEC      = 1.5;
static const double DEFAULT_TOWEL_LINE_PROXIMITY_PX            = 250.0;
static const int    DEFAULT_TOWEL_LINE_TRACK_MAX_MISSED_FRAMES = 90;

/* Per-station sensitivity defaults, used for any field missing from
 * a given station's "sensitivity" object. Values match what every
 * station in the original hardcoded buildStations() used. */
static const ConfigStationSensitivity DEFAULT_SENSITIVITY =
{
    0.30f,  /* track_iou_threshold */
    15,     /* track_max_missed_frames */
    0.55f,  /* keypoint_ema_alpha */
    10,     /* keypoint_invalid_dropout_frames */
    0.4,    /* movement_history_window_sec */
    30.0,   /* movement_speed_threshold */
    3,      /* upgrade_debounce_frames */
    5.0,    /* pending_washout_sec */
    3.5,    /* pending_away_washout_sec */
    1.75,   /* away_presence_washout_sec */
    1.75    /* fallback_active_confirm_sec */
};

/* ------------------------------------------------------------
 * Small helpers -- pull a field out of a cJSON object with a
 * fallback default, so every call site in config_load() below reads
 * as one line instead of a manual "does the key exist / is it the
 * right type" check every time.
 * ------------------------------------------------------------ */

static int json_get_int(const cJSON *obj, const char *key, int def)
{
    const cJSON *item = cJSON_GetObjectItemCaseSensitive(obj, key);
    if (cJSON_IsNumber(item))
    {
        return item->valueint;
    }
    return def;
}

static double json_get_double(const cJSON *obj, const char *key, double def)
{
    const cJSON *item = cJSON_GetObjectItemCaseSensitive(obj, key);
    if (cJSON_IsNumber(item))
    {
        return item->valuedouble;
    }
    return def;
}

static float json_get_float(const cJSON *obj, const char *key, float def)
{
    return (float)json_get_double(obj, key, (double)def);
}

static bool json_get_bool(const cJSON *obj, const char *key, bool def)
{
    const cJSON *item = cJSON_GetObjectItemCaseSensitive(obj, key);
    if (cJSON_IsBool(item))
    {
        return cJSON_IsTrue(item) ? true : false;
    }
    return def;
}

/* Copies a string field into a fixed-size buffer (truncating with a
 * warning if it doesn't fit) if present, else copies `def` in. */
static void json_get_string(const cJSON *obj, const char *key,
                            char *dest, size_t dest_size, const char *def)
{
    const cJSON *item = cJSON_GetObjectItemCaseSensitive(obj, key);
    const char *src = (cJSON_IsString(item) && item->valuestring != NULL)
                        ? item->valuestring
                        : def;

    if (src == NULL)
    {
        dest[0] = '\0';
        return;
    }

    size_t len = strlen(src);

    if (len >= dest_size)
    {
        fprintf(stderr,
                "config: WARNING \"%s\" value is %zu chars, truncating to %zu\n",
                key, len, dest_size - 1);
        len = dest_size - 1;
    }

    memcpy(dest, src, len);
    dest[len] = '\0';
}

/* REQUIRED string field -- returns false (and prints an error) if the
 * key is missing/empty, instead of silently falling back to a
 * default (there is no sane default for e.g. an RTSP URL). */
static bool json_require_string(const cJSON *obj, const char *key,
                                char *dest, size_t dest_size,
                                const char *context)
{
    const cJSON *item = cJSON_GetObjectItemCaseSensitive(obj, key);

    if (!cJSON_IsString(item) || item->valuestring == NULL || item->valuestring[0] == '\0')
    {
        fprintf(stderr, "config: ERROR missing required string \"%s\" in %s\n", key, context);
        return false;
    }

    json_get_string(obj, key, dest, dest_size, "");
    return true;
}

/* Parses a "roi": [[x,y], [x,y], ...] array into a fixed ConfigPoint
 * array. Returns the number of points parsed (0 if the key is absent
 * or not an array -- callers decide whether that's an error). */
static int json_get_roi(const cJSON *obj, const char *key,
                        ConfigPoint *out, int max_points)
{
    const cJSON *arr = cJSON_GetObjectItemCaseSensitive(obj, key);

    if (!cJSON_IsArray(arr))
    {
        return 0;
    }

    int count = 0;
    const cJSON *point = NULL;

    cJSON_ArrayForEach(point, arr)
    {
        if (count >= max_points)
        {
            fprintf(stderr,
                    "config: WARNING \"%s\" has more than %d points, truncating\n",
                    key, max_points);
            break;
        }

        if (!cJSON_IsArray(point) || cJSON_GetArraySize(point) < 2)
        {
            fprintf(stderr,
                    "config: WARNING \"%s\"[%d] is not a [x, y] pair, skipping\n",
                    key, count);
            continue;
        }

        const cJSON *x_item = cJSON_GetArrayItem(point, 0);
        const cJSON *y_item = cJSON_GetArrayItem(point, 1);

        if (!cJSON_IsNumber(x_item) || !cJSON_IsNumber(y_item))
        {
            fprintf(stderr,
                    "config: WARNING \"%s\"[%d] has non-numeric coordinates, skipping\n",
                    key, count);
            continue;
        }

        out[count].x = x_item->valueint;
        out[count].y = y_item->valueint;
        count++;
    }

    return count;
}

/* Parses a single "key": [x, y] pair (NOT an array of pairs -- that's
 * json_get_roi() above). Returns false if the key is missing or
 * isn't a well-formed 2-number array. */
static bool json_get_point(const cJSON *obj, const char *key, ConfigPoint *out)
{
    const cJSON *arr = cJSON_GetObjectItemCaseSensitive(obj, key);

    if (!cJSON_IsArray(arr) || cJSON_GetArraySize(arr) < 2)
    {
        return false;
    }

    const cJSON *x_item = cJSON_GetArrayItem(arr, 0);
    const cJSON *y_item = cJSON_GetArrayItem(arr, 1);

    if (!cJSON_IsNumber(x_item) || !cJSON_IsNumber(y_item))
    {
        return false;
    }

    out->x = x_item->valueint;
    out->y = y_item->valueint;
    return true;
}

static void parse_sensitivity(const cJSON *station_obj, ConfigStationSensitivity *out)
{
    *out = DEFAULT_SENSITIVITY;

    const cJSON *sens = cJSON_GetObjectItemCaseSensitive(station_obj, "sensitivity");

    if (!cJSON_IsObject(sens))
    {
        return; /* whole block absent -- every field stays at default */
    }

    out->track_iou_threshold =
        json_get_float(sens, "track_iou_threshold", out->track_iou_threshold);
    out->track_max_missed_frames =
        json_get_int(sens, "track_max_missed_frames", out->track_max_missed_frames);
    out->keypoint_ema_alpha =
        json_get_float(sens, "keypoint_ema_alpha", out->keypoint_ema_alpha);
    out->keypoint_invalid_dropout_frames =
        json_get_int(sens, "keypoint_invalid_dropout_frames", out->keypoint_invalid_dropout_frames);
    out->movement_history_window_sec =
        json_get_double(sens, "movement_history_window_sec", out->movement_history_window_sec);
    out->movement_speed_threshold =
        json_get_double(sens, "movement_speed_threshold", out->movement_speed_threshold);
    out->upgrade_debounce_frames =
        json_get_int(sens, "upgrade_debounce_frames", out->upgrade_debounce_frames);
    out->pending_washout_sec =
        json_get_double(sens, "pending_washout_sec", out->pending_washout_sec);
    out->pending_away_washout_sec =
        json_get_double(sens, "pending_away_washout_sec", out->pending_away_washout_sec);
    out->away_presence_washout_sec =
        json_get_double(sens, "away_presence_washout_sec", out->away_presence_washout_sec);
    out->fallback_active_confirm_sec =
        json_get_double(sens, "fallback_active_confirm_sec", out->fallback_active_confirm_sec);
}

/* "color": [b, g, r] -- defaults to white (255,255,255) if absent,
 * so a station missing a color still draws (just not distinctively). */
static void parse_color(const cJSON *station_obj, int *b, int *g, int *r)
{
    *b = 255;
    *g = 255;
    *r = 255;

    const cJSON *color = cJSON_GetObjectItemCaseSensitive(station_obj, "color");

    if (!cJSON_IsArray(color) || cJSON_GetArraySize(color) < 3)
    {
        return;
    }

    const cJSON *b_item = cJSON_GetArrayItem(color, 0);
    const cJSON *g_item = cJSON_GetArrayItem(color, 1);
    const cJSON *r_item = cJSON_GetArrayItem(color, 2);

    if (cJSON_IsNumber(b_item)) *b = b_item->valueint;
    if (cJSON_IsNumber(g_item)) *g = g_item->valueint;
    if (cJSON_IsNumber(r_item)) *r = r_item->valueint;
}

/*
 * config.json's "stations" is now an object keyed by line name:
 *   "stations": { "CTPAT": [ {...}, {...} ], "PACKING": [ ... ] }
 * instead of a flat array. This only picks out cfg->active_line's
 * array; everything below that point (per-station name/roi/color/
 * sensitivity parsing) is byte-for-byte the same as before the
 * line-grouping change.
 */
static bool parse_stations(const cJSON *root, AppConfig *cfg)
{
    const cJSON *stations_by_line = cJSON_GetObjectItemCaseSensitive(root, "stations");

    if (!cJSON_IsObject(stations_by_line))
    {
        fprintf(stderr,
                "config: ERROR \"stations\" is missing or not an object "
                "(expected { \"<line>\": [ ...stations... ] })\n");
        return false;
    }

    const cJSON *stations = cJSON_GetObjectItemCaseSensitive(stations_by_line, cfg->active_line);

    if (!cJSON_IsArray(stations))
    {
        fprintf(stderr,
                "config: ERROR \"stations\" has no array for active_line \"%s\" "
                "(check active_line matches one of the keys under \"stations\" exactly)\n",
                cfg->active_line);
        return false;
    }

    cfg->station_count = 0;

    const cJSON *station_obj = NULL;

    cJSON_ArrayForEach(station_obj, stations)
    {
        if (cfg->station_count >= CONFIG_MAX_STATIONS)
        {
            fprintf(stderr,
                    "config: WARNING more than %d stations for line \"%s\", truncating "
                    "(bump CONFIG_MAX_STATIONS in main_config_utils.h if you need more)\n",
                    CONFIG_MAX_STATIONS, cfg->active_line);
            break;
        }

        if (!cJSON_IsObject(station_obj))
        {
            fprintf(stderr, "config: WARNING stations.%s[%d] is not an object, skipping\n",
                    cfg->active_line, cfg->station_count);
            continue;
        }

        ConfigStation *cs = &cfg->stations[cfg->station_count];
        memset(cs, 0, sizeof(*cs));

        if (!json_require_string(station_obj, "name", cs->name, sizeof(cs->name), "a stations[] entry"))
        {
            return false;
        }

        cs->roi_count = json_get_roi(station_obj, "roi", cs->roi, CONFIG_MAX_ROI_POINTS);

        if (cs->roi_count < 3)
        {
            fprintf(stderr,
                    "config: ERROR station \"%s\" has %d ROI points (need at least 3 "
                    "to form a polygon)\n",
                    cs->name, cs->roi_count);
            return false;
        }

        parse_color(station_obj, &cs->color_b, &cs->color_g, &cs->color_r);
        parse_sensitivity(station_obj, &cs->sensitivity);

        cfg->station_count++;
    }

    if (cfg->station_count == 0)
    {
        fprintf(stderr, "config: ERROR stations.%s array is empty\n", cfg->active_line);
        return false;
    }

    return true;
}

/* Parses one shift's "breaks": [ {break_name, timings}, ... ] array.
 * Never fails the whole load -- a malformed break entry is just
 * skipped with a warning, since breaks are informational, not
 * required for the pipeline to run. */
static void parse_breaks(const cJSON *shift_obj, ConfigShift *out)
{
    out->break_count = 0;

    const cJSON *breaks = cJSON_GetObjectItemCaseSensitive(shift_obj, "breaks");

    if (!cJSON_IsArray(breaks))
    {
        return; /* a shift with no breaks is fine */
    }

    const cJSON *break_obj = NULL;

    cJSON_ArrayForEach(break_obj, breaks)
    {
        if (out->break_count >= CONFIG_MAX_BREAKS)
        {
            fprintf(stderr,
                    "config: WARNING shift \"%s\" has more than %d breaks, truncating\n",
                    out->shift_name, CONFIG_MAX_BREAKS);
            break;
        }

        if (!cJSON_IsObject(break_obj))
        {
            fprintf(stderr, "config: WARNING a break entry in shift \"%s\" is not an object, skipping\n",
                    out->shift_name);
            continue;
        }

        ConfigBreak *cb = &out->breaks[out->break_count];

        json_get_string(break_obj, "break_name", cb->break_name, sizeof(cb->break_name), "");
        json_get_string(break_obj, "timings", cb->timings, sizeof(cb->timings), "");

        out->break_count++;
    }
}

/*
 * Parses the top-level "shifts" array. Unlike "stations", this is
 * OPTIONAL -- if config.json has no "shifts" key at all,
 * cfg->shift_count is left at 0 and getCurrentShiftName()-style
 * lookups in ctpat.cpp just always return "unknown" rather than the
 * whole config load failing. A "shifts" key that IS present but
 * malformed (not an array) still only warns, for the same reason --
 * shift/break data doesn't gate whether the detection pipeline can
 * run at all.
 */
static void parse_shifts(const cJSON *root, AppConfig *cfg)
{
    cfg->shift_count = 0;

    const cJSON *shifts = cJSON_GetObjectItemCaseSensitive(root, "shifts");

    if (!cJSON_IsArray(shifts))
    {
        fprintf(stderr,
                "config: NOTE no \"shifts\" array in config.json -- "
                "current-shift lookup will be unavailable\n");
        return;
    }

    const cJSON *shift_obj = NULL;

    cJSON_ArrayForEach(shift_obj, shifts)
    {
        if (cfg->shift_count >= CONFIG_MAX_SHIFTS)
        {
            fprintf(stderr,
                    "config: WARNING more than %d shifts in config.json, truncating "
                    "(bump CONFIG_MAX_SHIFTS in main_config_utils.h if you need more)\n",
                    CONFIG_MAX_SHIFTS);
            break;
        }

        if (!cJSON_IsObject(shift_obj))
        {
            fprintf(stderr, "config: WARNING shifts[%d] is not an object, skipping\n", cfg->shift_count);
            continue;
        }

        ConfigShift *cs = &cfg->shifts[cfg->shift_count];
        memset(cs, 0, sizeof(*cs));

        json_get_string(shift_obj, "shift_name", cs->shift_name, sizeof(cs->shift_name), "");
        json_get_string(shift_obj, "timings", cs->timings, sizeof(cs->timings), "");
        cs->target_units = json_get_int(shift_obj, "target_units", 0);

        parse_breaks(shift_obj, cs);

        cfg->shift_count++;
    }
}

int config_load(const char *path, AppConfig *cfg)
{
    if (path == NULL || cfg == NULL)
    {
        fprintf(stderr, "config: ERROR NULL path or cfg passed to config_load()\n");
        return -1;
    }

    /* ---- Read the whole file into memory ---- */

    FILE *fp = fopen(path, "rb");

    if (fp == NULL)
    {
        fprintf(stderr, "config: ERROR could not open \"%s\" (does it exist?)\n", path);
        return -1;
    }

    fseek(fp, 0, SEEK_END);
    long file_size = ftell(fp);
    fseek(fp, 0, SEEK_SET);

    if (file_size <= 0)
    {
        fprintf(stderr, "config: ERROR \"%s\" is empty or unreadable\n", path);
        fclose(fp);
        return -1;
    }

    char *buffer = (char *)malloc((size_t)file_size + 1);

    if (buffer == NULL)
    {
        fprintf(stderr, "config: ERROR out of memory reading \"%s\" (%ld bytes)\n", path, file_size);
        fclose(fp);
        return -1;
    }

    size_t bytes_read = fread(buffer, 1, (size_t)file_size, fp);
    fclose(fp);
    buffer[bytes_read] = '\0';

    /* ---- Parse JSON ---- */

    cJSON *root = cJSON_Parse(buffer);
    free(buffer);

    if (root == NULL)
    {
        const char *err = cJSON_GetErrorPtr();
        fprintf(stderr, "config: ERROR failed to parse \"%s\" as JSON%s%s\n",
                path,
                err ? " near: " : "",
                err ? err : "");
        return -1;
    }

    memset(cfg, 0, sizeof(*cfg));

    /* ---- Required fields ---- */

    bool ok = true;

    ok = ok && json_require_string(root, "rtsp_url", cfg->rtsp_url, sizeof(cfg->rtsp_url), "config.json");
    ok = ok && json_require_string(root, "person_model", cfg->person_model, sizeof(cfg->person_model), "config.json");
    ok = ok && json_require_string(root, "pose_model", cfg->pose_model, sizeof(cfg->pose_model), "config.json");
    ok = ok && json_require_string(root, "towel_model", cfg->towel_model, sizeof(cfg->towel_model), "config.json");
    ok = ok && json_require_string(root, "active_line", cfg->active_line, sizeof(cfg->active_line), "config.json");

    if (!ok)
    {
        cJSON_Delete(root);
        return -1;
    }

    /* ---- Output / logging (all optional, defaulted) ---- */

    cfg->save_output_video = json_get_bool(root, "save_output_video", DEFAULT_SAVE_OUTPUT_VIDEO);
    json_get_string(root, "output_video_path", cfg->output_video_path, sizeof(cfg->output_video_path), DEFAULT_OUTPUT_VIDEO_PATH);
    json_get_string(root, "frame_log_path", cfg->frame_log_path, sizeof(cfg->frame_log_path), DEFAULT_FRAME_LOG_PATH);
    json_get_string(root, "db_path", cfg->db_path, sizeof(cfg->db_path), DEFAULT_DB_PATH);

    cfg->api_port = json_get_int(root, "api_port", DEFAULT_API_PORT);

    /* ---- Detection thresholds (all optional, defaulted) ---- */

    cfg->person_input_size     = json_get_int(root, "person_input_size", DEFAULT_PERSON_INPUT_SIZE);
    cfg->person_conf_threshold = json_get_float(root, "person_conf_threshold", DEFAULT_PERSON_CONF_THRESHOLD);
    cfg->nms_threshold         = json_get_float(root, "nms_threshold", DEFAULT_NMS_THRESHOLD);
    cfg->person_class_id       = json_get_int(root, "person_class_id", DEFAULT_PERSON_CLASS_ID);

    cfg->towel_input_size     = json_get_int(root, "towel_input_size", DEFAULT_TOWEL_INPUT_SIZE);
    cfg->towel_conf_threshold = json_get_float(root, "towel_conf_threshold", DEFAULT_TOWEL_CONF_THRESHOLD);
    cfg->towel_class_id       = json_get_int(root, "towel_class_id", DEFAULT_TOWEL_CLASS_ID);

    cfg->pose_input_size     = json_get_int(root, "pose_input_size", DEFAULT_POSE_INPUT_SIZE);
    cfg->pose_conf_threshold = json_get_float(root, "pose_conf_threshold", DEFAULT_POSE_CONF_THRESHOLD);

    cfg->min_track_box_area           = json_get_float(root, "min_track_box_area", DEFAULT_MIN_TRACK_BOX_AREA);
    cfg->roi_person_overlap_threshold = json_get_float(root, "roi_person_overlap_threshold", DEFAULT_ROI_PERSON_OVERLAP_THRESHOLD);

    /* ---- Conveyor belt ROI (optional -- display/unit-counter only) ---- */

    cfg->conveyor_belt_roi_count =
        json_get_roi(root, "conveyor_belt_roi", cfg->conveyor_belt_roi, CONFIG_MAX_ROI_POINTS);

    if (cfg->conveyor_belt_roi_count > 0 && cfg->conveyor_belt_roi_count < 3)
    {
        fprintf(stderr,
                "config: ERROR \"conveyor_belt_roi\" has %d points (need at least 3, or omit "
                "the key entirely to disable the conveyor overlay)\n",
                cfg->conveyor_belt_roi_count);
        cJSON_Delete(root);
        return -1;
    }

    /* ---- Towel counting line (required: two distinct points) ---- */

    const cJSON *towel_line = cJSON_GetObjectItemCaseSensitive(root, "towel_line");

    if (!cJSON_IsObject(towel_line))
    {
        fprintf(stderr, "config: ERROR missing required object \"towel_line\" in config.json\n");
        cJSON_Delete(root);
        return -1;
    }

    if (!json_get_point(towel_line, "p1", &cfg->towel_line_p1) ||
        !json_get_point(towel_line, "p2", &cfg->towel_line_p2))
    {
        fprintf(stderr,
                "config: ERROR \"towel_line\" needs both \"p1\": [x, y] and \"p2\": [x, y]\n");
        cJSON_Delete(root);
        return -1;
    }

    cfg->towel_line_bridge_max_gap_sec =
        json_get_double(towel_line, "bridge_max_gap_sec", DEFAULT_TOWEL_LINE_BRIDGE_MAX_GAP_SEC);
    cfg->towel_line_proximity_px =
        json_get_double(towel_line, "proximity_px", DEFAULT_TOWEL_LINE_PROXIMITY_PX);
    cfg->towel_line_track_max_missed_frames =
        json_get_int(towel_line, "track_max_missed_frames", DEFAULT_TOWEL_LINE_TRACK_MAX_MISSED_FRAMES);

    /* ---- Stations (required, at least one, from stations[active_line]) ---- */

    if (!parse_stations(root, cfg))
    {
        cJSON_Delete(root);
        return -1;
    }

    /* ---- Shifts + breaks (optional -- see parse_shifts()'s comment) ---- */

    parse_shifts(root, cfg);

    cJSON_Delete(root);

    fprintf(stderr,
            "config: loaded \"%s\" OK -- active_line=%s, %d station(s), %d shift(s), rtsp_url=%s\n",
            path, cfg->active_line, cfg->station_count, cfg->shift_count, cfg->rtsp_url);

    return 0;
}