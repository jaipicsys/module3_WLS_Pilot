/*
 * main_config_utils.h
 *
 * Loads config.json (RTSP URL, model paths, output/DB/API settings,
 * detection thresholds, the conveyor-belt ROI + towel counting line,
 * the active line's stations with their ROI polygons + 11-field
 * sensitivity block, and the shift/break schedule) into a plain-C
 * AppConfig struct that ctpat.cpp reads at startup.
 *
 * Deliberately plain C (no OpenCV / C++ types) so this header and
 * main_config_utils.c can be compiled and reused independently of
 * ctpat.cpp. ctpat.cpp converts the plain ConfigPoint/ConfigStation
 * arrays into cv::Point / Scalar / Station itself (see
 * applyConfigToRuntime() and buildStationsFromConfig() there).
 */

#ifndef MAIN_CONFIG_UTILS_H
#define MAIN_CONFIG_UTILS_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stdbool.h>

/* ------------------------------------------------------------
 * Sizing limits for the fixed-size arrays below. Bump these if a
 * real config.json needs more than this many points/stations --
 * everything here is a plain struct (no dynamic allocation), so a
 * limit has to exist somewhere.
 * ------------------------------------------------------------ */
#define CONFIG_MAX_ROI_POINTS   32
#define CONFIG_MAX_STATIONS     32
#define CONFIG_PATH_MAX         512
#define CONFIG_NAME_MAX         64
#define CONFIG_LINE_NAME_MAX    64
#define CONFIG_MAX_SHIFTS       8
#define CONFIG_MAX_BREAKS       8
#define CONFIG_SHIFT_NAME_MAX   32
#define CONFIG_BREAK_NAME_MAX   64
#define CONFIG_TIMINGS_MAX      32

typedef struct
{
    int x;
    int y;
} ConfigPoint;

/*
 * Mirrors StationSensitivity in ctpat.cpp field-for-field. See the
 * long comment above StationSensitivity in ctpat.cpp for what each
 * field actually controls at runtime -- the meanings are unchanged,
 * only the source (config.json instead of a hardcoded initializer
 * list) is new.
 */
typedef struct
{
    float  track_iou_threshold;
    int    track_max_missed_frames;
    float  keypoint_ema_alpha;
    int    keypoint_invalid_dropout_frames;
    double movement_history_window_sec;
    double movement_speed_threshold;
    int    upgrade_debounce_frames;
    double pending_washout_sec;
    double pending_away_washout_sec;
    double away_presence_washout_sec;
    double fallback_active_confirm_sec;
} ConfigStationSensitivity;

typedef struct
{
    char name[CONFIG_NAME_MAX];

    ConfigPoint roi[CONFIG_MAX_ROI_POINTS];
    int         roi_count;

    /* BGR, matching cv::Scalar's channel order (OpenCV is BGR, not RGB) */
    int color_b;
    int color_g;
    int color_r;

    ConfigStationSensitivity sensitivity;
} ConfigStation;

/*
 * One tea/lunch/meal break inside a shift. "timings" is kept as the
 * raw "HH:MM - HH:MM" string from config.json (not pre-parsed into
 * ints) -- ctpat.cpp's getCurrentShiftName()-style lookups parse a
 * timings string on the fly with sscanf() when they need minutes,
 * rather than this loader owning that parsing.
 */
typedef struct
{
    char break_name[CONFIG_BREAK_NAME_MAX];
    char timings[CONFIG_TIMINGS_MAX];
} ConfigBreak;

typedef struct
{
    char shift_name[CONFIG_SHIFT_NAME_MAX];
    char timings[CONFIG_TIMINGS_MAX];   /* raw "HH:MM - HH:MM" */
    int  target_units;

    ConfigBreak breaks[CONFIG_MAX_BREAKS];
    int         break_count;
} ConfigShift;

typedef struct
{
    /* ---- Video source ---- */
    char rtsp_url[CONFIG_PATH_MAX];

    /* ---- Model paths ---- */
    char person_model[CONFIG_PATH_MAX];
    char pose_model[CONFIG_PATH_MAX];
    char towel_model[CONFIG_PATH_MAX];

    /* ---- Output / logging ---- */
    bool save_output_video;
    char output_video_path[CONFIG_PATH_MAX];
    char frame_log_path[CONFIG_PATH_MAX];
    char db_path[CONFIG_PATH_MAX];

    /* ---- HTTP API ---- */
    int api_port;

    /* ---- Detection: person model ---- */
    int   person_input_size;
    float person_conf_threshold;
    float nms_threshold;
    int   person_class_id;

    /* ---- Detection: towel model ---- */
    int   towel_input_size;
    float towel_conf_threshold;
    int   towel_class_id;

    /* ---- Detection: pose model ---- */
    int   pose_input_size;
    float pose_conf_threshold;

    /* ---- Tracking / ROI tuning ---- */
    float min_track_box_area;
    float roi_person_overlap_threshold;

    /* ---- Conveyor belt ROI (unit-counter display only) ---- */
    ConfigPoint conveyor_belt_roi[CONFIG_MAX_ROI_POINTS];
    int         conveyor_belt_roi_count;

    /* ---- Towel counting line ---- */
    ConfigPoint towel_line_p1;
    ConfigPoint towel_line_p2;
    double      towel_line_bridge_max_gap_sec;
    double      towel_line_proximity_px;
    int         towel_line_track_max_missed_frames;

    /* ---- Which line's station group to run (config.json's
     *      "stations" is now { "<line>": [ ...stations... ] } --
     *      this picks one key out of that object at load time; the
     *      rest of this struct, and all of ctpat.cpp downstream,
     *      never sees the other lines). ---- */
    char active_line[CONFIG_LINE_NAME_MAX];

    /* ---- Stations (active/idle/away state machine) -- the
     *      "stations"[active_line] array, flattened here exactly as
     *      before the line-grouping change. ---- */
    ConfigStation stations[CONFIG_MAX_STATIONS];
    int           station_count;

    /* ---- Shifts + breaks (for current-shift lookup / target_units
     *      tracking; see getCurrentShiftName() in ctpat.cpp). Optional
     *      -- shift_count is 0 if config.json has no "shifts" array. ---- */
    ConfigShift shifts[CONFIG_MAX_SHIFTS];
    int         shift_count;
} AppConfig;

/*
 * Loads and validates config.json from `path` into `cfg`.
 *
 * Returns 0 on success. Returns -1 on failure (file not found,
 * malformed JSON, or a required field missing/wrong type) and prints
 * a specific error to stderr describing what was wrong -- the caller
 * doesn't need to inspect `cfg` after a -1 return, its contents are
 * unspecified in that case.
 *
 * `cfg` does not need to be zero-initialized first; config_load()
 * fills every field it defines (applying the defaults documented in
 * config.json's own comments -- see DEFAULT_* in main_config_utils.c
 * -- for any optional field that's simply absent from the file).
 */
int config_load(const char *path, AppConfig *cfg);

#ifdef __cplusplus
}
#endif

#endif /* MAIN_CONFIG_UTILS_H */