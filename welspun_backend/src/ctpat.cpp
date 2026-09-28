#include <opencv2/opencv.hpp>
#include <onnxruntime_cxx_api.h>

#include "BYTETracker.h"   // defines struct Object { rect, label, prob }, STrack, BYTETracker
#include "db.h"            // SQLite logging layer (station_timers + product_produced)
#include "main_config_utils.h"

#include "ctpat.hpp"

#include <iostream>
#include <vector>
#include <string>
#include <algorithm>
#include <cmath>
#include <chrono>
#include <iomanip>
#include <csignal>
#include <array>
#include <deque>
#include <tuple>
#include <sstream>
#include <unordered_map>
#include <unordered_set>
#include <stdio.h>
#include <fstream>
#include <ctime>
#include <thread>
#include <mutex>
#include <condition_variable>
#include <atomic>

using namespace cv;
using namespace std;


// ============================================================
// CONFIGURATION
// ============================================================

static int   PERSON_INPUT_SIZE      = 640;
static float PERSON_CONF_THRESHOLD  = 0.50f;
static float NMS_THRESHOLD          = 0.45f;
static int   PERSON_CLASS_ID        = 0;   // YOLO COCO "person"

static int   TOWEL_INPUT_SIZE     = 640;
static float TOWEL_CONF_THRESHOLD = 0.50f;
static int   TOWEL_CLASS_ID       = 0;   // only class in towel.onnx

static int   POSE_INPUT_SIZE     = 640;
static float POSE_CONF_THRESHOLD = 0.50f;

// Minimum tracked-box area (px^2) to draw in the on-screen overlay only.
static float MIN_TRACK_BOX_AREA = 100.0f;


// ============================================================
// COCO POSE KEYPOINTS
// ============================================================

static const int NUM_KEYPOINTS = 17;

static const int LEFT_SHOULDER  = 5;
static const int RIGHT_SHOULDER = 6;
static const int LEFT_ELBOW     = 7;
static const int RIGHT_ELBOW    = 8;
static const int LEFT_WRIST     = 9;
static const int RIGHT_WRIST    = 10;

struct SidePoints { int wrist; int elbow; int shoulder; };

static const SidePoints LEFT_SIDE  = { LEFT_WRIST,  LEFT_ELBOW,  LEFT_SHOULDER };
static const SidePoints RIGHT_SIDE = { RIGHT_WRIST, RIGHT_ELBOW, RIGHT_SHOULDER };
static const array<SidePoints, 2> SIDES = { LEFT_SIDE, RIGHT_SIDE };

static const vector<int> TRACKED_KEYPOINTS =
{
    5, 6, 7, 8, 9, 10   // shoulders, elbows, wrists
};


// ============================================================
// PER-STATION SENSITIVITY
// ============================================================

struct StationSensitivity
{
    // --- Consumed GLOBALLY: only the FIRST station's values for
    //     these 4 are actually used (see computeGlobalTrackingParams()). ---
    float  track_iou_threshold             = 0.30f;
    int    track_max_missed_frames         = 15;
    float  keypoint_ema_alpha              = 0.35f;
    int    keypoint_invalid_dropout_frames = 10;

    // --- Consumed PER-STATION ---
    double movement_history_window_sec = 0.4;
    double movement_speed_threshold    = 30.0;
    int    upgrade_debounce_frames     = 3;
    double pending_washout_sec         = 5.0;
    double pending_away_washout_sec    = 3.5;
    double away_presence_washout_sec   = 1.75;
    double fallback_active_confirm_sec = 1.75;
};


// ============================================================
// STRUCTURES  (detection / pose)
// ============================================================

struct Detection
{
    Rect box;
    float confidence;
};

struct Keypoint
{
    Point2f point;
    float confidence;
    bool valid;
};

struct PersonPose
{
    vector<Keypoint> keypoints;
};


// ============================================================
// ROIs (loaded from config.json)
// ============================================================

static vector<Point> g_conveyor_belt_roi;

static long long          g_units_produced = 0;
static unordered_set<int> g_counted_towel_ids;


// ============================================================
// STATIONS
// ============================================================

enum class StationState { ACTIVE, IDLE, AWAY };

struct Station
{
    string name;
    vector<Point> roi;
    Scalar color;

    StationSensitivity sensitivity{};

    StationState state = StationState::ACTIVE;

    // --- Upgrade path ---
    StationState upgrade_candidate = StationState::AWAY;
    int          upgrade_pending_count = 0;

    // --- Downgrade path ---
    bool         is_pending = false;
    StationState pending_from   = StationState::AWAY;
    StationState pending_target = StationState::AWAY;
    double       pending_elapsed_ms = 0.0;

    // --- AWAY-state presence suspicion ---
    bool         is_away_pending = false;
    StationState away_pending_target = StationState::AWAY;
    double       away_pending_elapsed_ms = 0.0;

    // --- Elbow/shoulder fallback-active confirmation ---
    bool         is_fallback_pending = false;
    double       fallback_pending_elapsed_ms = 0.0;

    double active_ms = 0.0;
    double idle_ms   = 0.0;
    double away_ms   = 0.0;

    // --- DB state-change logging ---
    StationState logged_state = StationState::ACTIVE;
    double       logged_state_start_sec = 0.0;
};

static vector<Station> g_stations;

// ------------------------------------------------------------
// GLOBAL TRACKING PARAMETERS
// ------------------------------------------------------------

static float  g_track_iou_threshold             = 0.30f;
static int    g_track_max_missed_frames         = 15;
static float  g_keypoint_ema_alpha              = 0.35f;
static int    g_keypoint_invalid_dropout_frames = 10;

static double g_keypoint_history_retention_sec = 0.4;

static void computeGlobalTrackingParams()
{
    if (g_stations.empty())
    {
        return;
    }

    const Station& primary = g_stations.front();

    g_track_iou_threshold             = primary.sensitivity.track_iou_threshold;
    g_track_max_missed_frames         = primary.sensitivity.track_max_missed_frames;
    g_keypoint_ema_alpha              = primary.sensitivity.keypoint_ema_alpha;
    g_keypoint_invalid_dropout_frames = primary.sensitivity.keypoint_invalid_dropout_frames;

    double max_window = primary.sensitivity.movement_history_window_sec;

    for (size_t i = 0; i < g_stations.size(); i++)
    {
        const Station& station = g_stations[i];

        max_window = max(max_window, station.sensitivity.movement_history_window_sec);

        if (i == 0)
        {
            continue;
        }

        if (station.sensitivity.track_iou_threshold != primary.sensitivity.track_iou_threshold ||
            station.sensitivity.track_max_missed_frames != primary.sensitivity.track_max_missed_frames ||
            station.sensitivity.keypoint_ema_alpha != primary.sensitivity.keypoint_ema_alpha ||
            station.sensitivity.keypoint_invalid_dropout_frames != primary.sensitivity.keypoint_invalid_dropout_frames)
        {
            cerr << "WARNING: station \"" << station.name << "\" specifies different "
                 << "track_iou_threshold / track_max_missed_frames / keypoint_ema_alpha / "
                 << "keypoint_invalid_dropout_frames than the first station (\""
                 << primary.name << "\"). Only \"" << primary.name << "\"'s values for these "
                 << "4 fields are actually in effect -- \"" << station.name
                 << "\"'s differing values are ignored." << endl;
        }
    }

    g_keypoint_history_retention_sec = max_window;
}

// TO ADD A NEW STATION: add an entry to "stations" in config.json.
static void buildStationsFromConfig()
{
    g_stations.clear();

    for (int i = 0; i < g_cfg.station_count; i++)
    {
        const ConfigStation& cs = g_cfg.stations[i];

        Station station;
        station.name = cs.name;

        for (int p = 0; p < cs.roi_count; p++)
        {
            station.roi.push_back(Point(cs.roi[p].x, cs.roi[p].y));
        }

        station.color = Scalar(cs.color_b, cs.color_g, cs.color_r);

        station.sensitivity.track_iou_threshold             = cs.sensitivity.track_iou_threshold;
        station.sensitivity.track_max_missed_frames         = cs.sensitivity.track_max_missed_frames;
        station.sensitivity.keypoint_ema_alpha              = cs.sensitivity.keypoint_ema_alpha;
        station.sensitivity.keypoint_invalid_dropout_frames = cs.sensitivity.keypoint_invalid_dropout_frames;
        station.sensitivity.movement_history_window_sec     = cs.sensitivity.movement_history_window_sec;
        station.sensitivity.movement_speed_threshold        = cs.sensitivity.movement_speed_threshold;
        station.sensitivity.upgrade_debounce_frames         = cs.sensitivity.upgrade_debounce_frames;
        station.sensitivity.pending_washout_sec             = cs.sensitivity.pending_washout_sec;
        station.sensitivity.pending_away_washout_sec        = cs.sensitivity.pending_away_washout_sec;
        station.sensitivity.away_presence_washout_sec       = cs.sensitivity.away_presence_washout_sec;
        station.sensitivity.fallback_active_confirm_sec     = cs.sensitivity.fallback_active_confirm_sec;

        g_stations.push_back(station);
    }

    if (g_stations.empty())
    {
        cerr << "WARNING: config.json defined 0 stations -- the active/idle/away "
             << "state machine will have nothing to report on." << endl;
    }
}


// ============================================================
// PER-TRACK KEYPOINT-SMOOTHING STATE  (keyed by BYTETrack track_id)
// ============================================================

struct Track
{
    int id = -1;
    Rect box;

    int missed_frames = 0;
    bool matched_this_frame = false;

    array<Point2f, NUM_KEYPOINTS> ema_point{};
    array<float, NUM_KEYPOINTS>   ema_conf{};
    array<bool, NUM_KEYPOINTS>    ema_valid{};
    array<int, NUM_KEYPOINTS>     invalid_streak{};

    array<deque<pair<double, Point2f>>, NUM_KEYPOINTS> keypoint_history{};
};

static unordered_map<int, Track> g_tracks;


static float boxIoU(const Rect& a, const Rect& b)
{
    Rect inter = a & b;
    float inter_area = (float)inter.area();

    if (inter_area <= 0.0f)
    {
        return 0.0f;
    }

    float union_area = (float)(a.area() + b.area()) - inter_area;

    return union_area > 0.0f ? inter_area / union_area : 0.0f;
}


static bool isKeypointMoving(
    const deque<pair<double, Point2f>>& history,
    double window_sec,
    double speed_threshold)
{
    if (history.size() < 2)
    {
        return false;
    }

    double newest_time = history.back().first;
    double cutoff_time = newest_time - window_sec;

    size_t start_idx = 0;

    while (start_idx < history.size() && history[start_idx].first < cutoff_time)
    {
        start_idx++;
    }

    if (start_idx >= history.size() - 1)
    {
        return false;
    }

    double dt = history.back().first - history[start_idx].first;

    if (dt <= 0.0)
    {
        return false;
    }

    double path_length = 0.0;

    for (size_t i = start_idx + 1; i < history.size(); i++)
    {
        path_length += norm(history[i].second - history[i - 1].second);
    }

    double speed = path_length / dt;

    return speed > speed_threshold;
}


static void syncTracksWithByteTrack(
    const vector<STrack>& output_stracks,
    const vector<Detection>& person_dets,
    const vector<PersonPose>& raw_poses,
    double video_time_sec)
{
    size_t n = person_dets.size();
    size_t m = output_stracks.size();

    vector<tuple<float, size_t, size_t>> candidates; // iou, strack_idx, det_idx

    for (size_t s = 0; s < m; s++)
    {
        const vector<float>& tlwh = output_stracks[s].tlwh;

        Rect strack_box((int)tlwh[0], (int)tlwh[1], (int)tlwh[2], (int)tlwh[3]);

        for (size_t i = 0; i < n; i++)
        {
            float iou = boxIoU(strack_box, person_dets[i].box);

            if (iou >= g_track_iou_threshold)
            {
                candidates.push_back({ iou, s, i });
            }
        }
    }

    sort(candidates.begin(), candidates.end(),
        [](const tuple<float, size_t, size_t>& a, const tuple<float, size_t, size_t>& b)
        {
            return get<0>(a) > get<0>(b);
        });

    vector<int> strack_to_det(m, -1);
    vector<bool> strack_used(m, false);
    vector<bool> det_used(n, false);

    for (auto& c : candidates)
    {
        size_t s = get<1>(c);
        size_t i = get<2>(c);

        if (strack_used[s] || det_used[i])
        {
            continue;
        }

        strack_used[s] = true;
        det_used[i] = true;
        strack_to_det[s] = (int)i;
    }

    unordered_set<int> seen_ids;
    seen_ids.reserve(m);

    for (size_t s = 0; s < m; s++)
    {
        int track_id = output_stracks[s].track_id;
        seen_ids.insert(track_id);

        Track& track = g_tracks[track_id]; // creates on first sight
        track.id = track_id;

        const vector<float>& tlwh = output_stracks[s].tlwh;
        track.box = Rect((int)tlwh[0], (int)tlwh[1], (int)tlwh[2], (int)tlwh[3]);

        track.missed_frames = 0;

        int det_idx = strack_to_det[s];

        if (det_idx < 0)
        {
            track.matched_this_frame = false;
            continue;
        }

        track.matched_this_frame = true;

        const PersonPose& raw = raw_poses[det_idx];

        for (int k : TRACKED_KEYPOINTS)
        {
            if (raw.keypoints[k].valid)
            {
                if (!track.ema_valid[k])
                {
                    track.ema_point[k] = raw.keypoints[k].point;
                }
                else
                {
                    track.ema_point[k] =
                        g_keypoint_ema_alpha * raw.keypoints[k].point +
                        (1.0f - g_keypoint_ema_alpha) * track.ema_point[k];
                }

                track.ema_conf[k] = raw.keypoints[k].confidence;
                track.ema_valid[k] = true;
                track.invalid_streak[k] = 0;

                track.keypoint_history[k].push_back({ video_time_sec, track.ema_point[k] });
            }
            else
            {
                track.invalid_streak[k]++;

                if (track.invalid_streak[k] > g_keypoint_invalid_dropout_frames)
                {
                    track.ema_valid[k] = false;
                }
            }
        }

        for (int k : TRACKED_KEYPOINTS)
        {
            while (!track.keypoint_history[k].empty() &&
                   video_time_sec - track.keypoint_history[k].front().first > g_keypoint_history_retention_sec)
            {
                track.keypoint_history[k].pop_front();
            }
        }
    }

    for (auto& entry : g_tracks)
    {
        if (seen_ids.find(entry.first) == seen_ids.end())
        {
            entry.second.missed_frames++;
        }
    }

    for (auto it = g_tracks.begin(); it != g_tracks.end(); )
    {
        if (it->second.missed_frames > g_track_max_missed_frames)
        {
            it = g_tracks.erase(it);
        }
        else
        {
            ++it;
        }
    }
}


// ============================================================
// GEOMETRY HELPERS
// ============================================================

static bool pointInROI(const Point2f& pt, const vector<Point>& roi)
{
    return pointPolygonTest(roi, pt, false) >= 0;
}

static float ROI_PERSON_OVERLAP_THRESHOLD = 0.15f;

static bool boxOverlapsROI(const Rect& box, const vector<Point>& roi)
{
    vector<Point> box_pts =
    {
        Point(box.x, box.y),
        Point(box.x + box.width, box.y),
        Point(box.x + box.width, box.y + box.height),
        Point(box.x, box.y + box.height)
    };

    vector<Point> intersection;

    float intersection_area =
        intersectConvexConvex(box_pts, roi, intersection, true);

    if (intersection_area <= 0.0f)
    {
        return false;
    }

    float person_box_area = (float)box.area();

    if (person_box_area <= 0.0f)
    {
        return false;
    }

    float overlap_ratio = intersection_area / person_box_area;

    return overlap_ratio >= ROI_PERSON_OVERLAP_THRESHOLD;
}


// ============================================================
// TOWEL UNIT COUNTER  (line-crossing, conveyor belt)
// ============================================================

static Point2f TOWEL_LINE_P1(555.0f, 1510.0f);
static Point2f TOWEL_LINE_P2(133.0f, 790.0f);

static float lineSideValue(const Point2f& p)
{
    return (TOWEL_LINE_P2.x - TOWEL_LINE_P1.x) * (p.y - TOWEL_LINE_P1.y) -
           (TOWEL_LINE_P2.y - TOWEL_LINE_P1.y) * (p.x - TOWEL_LINE_P1.x);
}

static float TOWEL_BEFORE_SIGN = 0.0f;

static bool isBeforeLine(const Point2f& p)
{
    float v = lineSideValue(p);
    return (v >= 0.0f) == (TOWEL_BEFORE_SIGN >= 0.0f);
}

static double pointToSegmentDistance(const Point2f& p, const Point2f& a, const Point2f& b)
{
    Point2f ab = b - a;
    float len_sq = ab.x * ab.x + ab.y * ab.y;

    float t = 0.0f;

    if (len_sq > 1e-6f)
    {
        t = ((p.x - a.x) * ab.x + (p.y - a.y) * ab.y) / len_sq;
        t = max(0.0f, min(1.0f, t));
    }

    Point2f proj(a.x + ab.x * t, a.y + ab.y * t);

    return norm(p - proj);
}

static double TOWEL_LINE_BRIDGE_MAX_GAP_SEC = 1.5;
static double TOWEL_LINE_PROXIMITY_PX = 250.0;
static int TOWEL_LINE_TRACK_MAX_MISSED_FRAMES = 90;

// MUST be called after TOWEL_LINE_P1/P2 are set from config.
static void initTowelLine()
{
    TOWEL_BEFORE_SIGN = lineSideValue(
        Point2f(
            max(TOWEL_LINE_P1.x, TOWEL_LINE_P2.x) + 500.0f,
            (TOWEL_LINE_P1.y + TOWEL_LINE_P2.y) * 0.5f
        )
    );
}

struct TowelLineTrackState
{
    bool    is_before = true;
    Point2f last_center;
    double  last_update_sec = 0.0;
    int     missed_frames   = 0;
    bool    counted         = false;
};

static unordered_map<int, TowelLineTrackState> g_towel_line_tracks;

struct LostNearLineCandidate
{
    Point2f last_center;
    double  last_seen_sec;
};

static vector<LostNearLineCandidate> g_lost_near_line;

static void updateTowelCount(const vector<STrack>& towel_stracks, double video_time_sec)
{
    unordered_set<int> ids_this_frame;
    ids_this_frame.reserve(towel_stracks.size());

    for (const STrack& t : towel_stracks)
    {
        int id = t.track_id;
        ids_this_frame.insert(id);

        const vector<float>& tlwh = t.tlwh;

        Point2f center(
            tlwh[0] + tlwh[2] * 0.5f,
            tlwh[1] + tlwh[3] * 0.5f
        );

        bool currently_before = isBeforeLine(center);

        auto it = g_towel_line_tracks.find(id);

        if (it == g_towel_line_tracks.end())
        {
            TowelLineTrackState st;
            st.is_before = currently_before;
            st.last_center = center;
            st.last_update_sec = video_time_sec;
            st.missed_frames = 0;

            g_towel_line_tracks[id] = st;

            if (!currently_before)
            {
                double perp_dist = pointToSegmentDistance(center, TOWEL_LINE_P1, TOWEL_LINE_P2);

                if (perp_dist <= TOWEL_LINE_PROXIMITY_PX)
                {
                    for (size_t ci = 0; ci < g_lost_near_line.size(); ci++)
                    {
                        const LostNearLineCandidate& cand = g_lost_near_line[ci];

                        double gap_sec = video_time_sec - cand.last_seen_sec;

                        if (gap_sec < 0.0 || gap_sec > TOWEL_LINE_BRIDGE_MAX_GAP_SEC)
                        {
                            continue;
                        }

                        double cand_perp = pointToSegmentDistance(cand.last_center, TOWEL_LINE_P1, TOWEL_LINE_P2);

                        if (cand_perp > TOWEL_LINE_PROXIMITY_PX)
                        {
                            continue;
                        }

                        g_towel_line_tracks[id].counted = true;
                        g_counted_towel_ids.insert(id);
                        g_lost_near_line.erase(g_lost_near_line.begin() + ci);

                        g_units_produced++;
                        db_log_product(getCurrentShiftTimings().c_str());
                        break;
                    }
                }
            }

            continue;
        }

        TowelLineTrackState& st = it->second;

        if (!st.counted && st.is_before && !currently_before)
        {
            st.counted = true;
            g_counted_towel_ids.insert(id);

            g_units_produced++;
            db_log_product(getCurrentShiftTimings().c_str());
        }
        else if (st.counted)
        {
            g_counted_towel_ids.insert(id);
        }

        st.is_before = currently_before;
        st.last_center = center;
        st.last_update_sec = video_time_sec;
        st.missed_frames = 0;
    }

    for (auto it = g_towel_line_tracks.begin(); it != g_towel_line_tracks.end(); )
    {
        if (ids_this_frame.find(it->first) != ids_this_frame.end())
        {
            ++it;
            continue;
        }

        it->second.missed_frames++;

        if (it->second.missed_frames == 1 && !it->second.counted && it->second.is_before)
        {
            double perp = pointToSegmentDistance(it->second.last_center, TOWEL_LINE_P1, TOWEL_LINE_P2);

            if (perp <= TOWEL_LINE_PROXIMITY_PX)
            {
                LostNearLineCandidate cand;
                cand.last_center = it->second.last_center;
                cand.last_seen_sec = it->second.last_update_sec;

                g_lost_near_line.push_back(cand);
            }
        }

        if (it->second.missed_frames > TOWEL_LINE_TRACK_MAX_MISSED_FRAMES)
        {
            it = g_towel_line_tracks.erase(it);
        }
        else
        {
            ++it;
        }
    }

    g_lost_near_line.erase(
        remove_if(
            g_lost_near_line.begin(),
            g_lost_near_line.end(),
            [video_time_sec](const LostNearLineCandidate& cand)
            {
                return (video_time_sec - cand.last_seen_sec) > TOWEL_LINE_BRIDGE_MAX_GAP_SEC;
            }
        ),
        g_lost_near_line.end()
    );
}

static void drawTowelLine(Mat& frame)
{
    line(frame, Point((int)TOWEL_LINE_P1.x, (int)TOWEL_LINE_P1.y),
                Point((int)TOWEL_LINE_P2.x, (int)TOWEL_LINE_P2.y),
                Scalar(0, 0, 255), 3);

    putText(frame, "COUNT LINE",
        Point((int)TOWEL_LINE_P2.x, (int)TOWEL_LINE_P2.y - 10),
        FONT_HERSHEY_SIMPLEX, 0.7, Scalar(0, 0, 255), 2);
}


static string formatHHMMSS(double total_ms)
{
    long long total_seconds = (long long)(total_ms / 1000.0);

    long long hh = total_seconds / 3600;
    long long mm = (total_seconds % 3600) / 60;
    long long ss = total_seconds % 60;

    ostringstream oss;

    oss << setw(2) << setfill('0') << hh << ":"
        << setw(2) << setfill('0') << mm << ":"
        << setw(2) << setfill('0') << ss;

    return oss.str();
}


// ============================================================
// STATION STATE MACHINE
// ============================================================

static int statePriority(StationState s)
{
    switch (s)
    {
        case StationState::AWAY:   return 0;
        case StationState::IDLE:   return 1;
        case StationState::ACTIVE: return 2;
    }
    return 0;
}

static void creditStationTime(Station& station, StationState target, double ms)
{
    switch (target)
    {
        case StationState::ACTIVE: station.active_ms += ms; break;
        case StationState::IDLE:   station.idle_ms   += ms; break;
        case StationState::AWAY:   station.away_ms   += ms; break;
    }
}

static double pendingWashoutMsFor(const Station& station, StationState target)
{
    if (target == StationState::AWAY)
    {
        return station.sensitivity.pending_away_washout_sec * 1000.0;
    }

    return station.sensitivity.pending_washout_sec * 1000.0;
}

static void updateStations(double frame_dt_sec)
{
    double frame_dt_ms = frame_dt_sec * 1000.0;

    for (auto& station : g_stations)
    {
        bool any_present = false;
        bool any_wrist_active = false;
        bool any_fallback_active_raw = false;

        for (auto& kv : g_tracks)
        {
            Track& track = kv.second;

            if (!boxOverlapsROI(track.box, station.roi))
            {
                continue;
            }

            any_present = true;

            for (const SidePoints& side : SIDES)
            {
                if (track.ema_valid[side.wrist])
                {
                    if (pointInROI(track.ema_point[side.wrist], station.roi) &&
                        isKeypointMoving(
                            track.keypoint_history[side.wrist],
                            station.sensitivity.movement_history_window_sec,
                            station.sensitivity.movement_speed_threshold))
                    {
                        any_wrist_active = true;
                    }
                }
                else
                {
                    for (int k : { side.elbow, side.shoulder })
                    {
                        if (track.ema_valid[k] &&
                            pointInROI(track.ema_point[k], station.roi) &&
                            isKeypointMoving(
                                track.keypoint_history[k],
                                station.sensitivity.movement_history_window_sec,
                                station.sensitivity.movement_speed_threshold))
                        {
                            any_fallback_active_raw = true;
                            break;
                        }
                    }
                }
            }
        }

        bool any_active = false;

        if (any_wrist_active)
        {
            any_active = true;

            station.is_fallback_pending = false;
            station.fallback_pending_elapsed_ms = 0.0;
        }
        else if (any_fallback_active_raw)
        {
            station.fallback_pending_elapsed_ms =
                station.is_fallback_pending
                    ? station.fallback_pending_elapsed_ms + frame_dt_ms
                    : frame_dt_ms;

            station.is_fallback_pending = true;

            if (station.fallback_pending_elapsed_ms >=
                station.sensitivity.fallback_active_confirm_sec * 1000.0)
            {
                any_active = true;
            }
        }
        else
        {
            station.is_fallback_pending = false;
            station.fallback_pending_elapsed_ms = 0.0;
        }

        StationState desired;

        if (!any_present)
        {
            desired = StationState::AWAY;
        }
        else if (any_active)
        {
            desired = StationState::ACTIVE;
        }
        else
        {
            desired = StationState::IDLE;
        }

        if (station.state == StationState::AWAY && !station.is_pending)
        {
            if (!station.is_away_pending)
            {
                if (desired != StationState::AWAY)
                {
                    station.is_away_pending = true;
                    station.away_pending_target = desired;
                    station.away_pending_elapsed_ms = frame_dt_ms;
                }
            }
            else
            {
                if (desired == StationState::AWAY)
                {
                    creditStationTime(
                        station,
                        StationState::AWAY,
                        station.away_pending_elapsed_ms
                    );

                    station.is_away_pending = false;
                    station.away_pending_elapsed_ms = 0.0;
                }
                else
                {
                    station.away_pending_target = desired;
                    station.away_pending_elapsed_ms += frame_dt_ms;

                    if (station.away_pending_elapsed_ms >=
                        station.sensitivity.away_presence_washout_sec * 1000.0)
                    {
                        creditStationTime(
                            station,
                            station.away_pending_target,
                            station.away_pending_elapsed_ms
                        );

                        station.state = station.away_pending_target;
                        station.is_away_pending = false;
                        station.away_pending_elapsed_ms = 0.0;
                    }
                }
            }
        }
        else if (!station.is_pending)
        {
            if (desired == station.state)
            {
                station.upgrade_pending_count = 0;
            }
            else if (statePriority(desired) > statePriority(station.state))
            {
                if (desired == station.upgrade_candidate)
                {
                    station.upgrade_pending_count++;
                }
                else
                {
                    station.upgrade_candidate = desired;
                    station.upgrade_pending_count = 1;
                }

                if (station.upgrade_pending_count >=
                    station.sensitivity.upgrade_debounce_frames)
                {
                    station.state = desired;
                    station.upgrade_pending_count = 0;
                }
            }
            else
            {
                station.is_pending = true;
                station.pending_from = station.state;
                station.pending_target = desired;
                station.pending_elapsed_ms = frame_dt_ms;

                station.upgrade_pending_count = 0;
            }
        }
        else
        {
            if (desired == station.pending_from)
            {
                creditStationTime(
                    station,
                    station.pending_from,
                    station.pending_elapsed_ms
                );

                station.is_pending = false;
                station.pending_elapsed_ms = 0.0;
            }
            else
            {
                station.pending_target = desired;
                station.pending_elapsed_ms += frame_dt_ms;

                double washout_ms = pendingWashoutMsFor(station, station.pending_target);

                if (station.pending_elapsed_ms >= washout_ms)
                {
                    creditStationTime(
                        station,
                        station.pending_target,
                        station.pending_elapsed_ms
                    );

                    station.state = station.pending_target;
                    station.is_pending = false;
                    station.pending_elapsed_ms = 0.0;
                }
            }
        }

        if (!station.is_pending && !station.is_away_pending)
        {
            creditStationTime(
                station,
                station.state,
                frame_dt_ms
            );
        }
    }
}


// ============================================================
// DISPLAY TEXT HELPERS
// ============================================================

static string stationStateName(StationState s)
{
    switch (s)
    {
        case StationState::ACTIVE: return "ACTIVE";
        case StationState::IDLE:   return "IDLE";
        case StationState::AWAY:   return "AWAY";
    }
    return "?";
}

static string stationDisplayStateText(const Station& station)
{
    if (station.is_pending)
    {
        return stationStateName(station.pending_from) + "(P)";
    }

    if (station.is_away_pending)
    {
        return stationStateName(StationState::AWAY) + "(P)";
    }

    return stationStateName(station.state);
}


// ============================================================
// DATABASE STATE-CHANGE LOGGING
// ============================================================

static void logStationStateChanges(double video_time_sec)
{
    for (auto& station : g_stations)
    {
        if (station.state == station.logged_state)
        {
            continue;
        }

        double duration_sec = video_time_sec - station.logged_state_start_sec;

        db_log_station_state(
            station.name.c_str(),
            stationStateName(station.logged_state).c_str(),
            duration_sec,
            getCurrentShiftTimings().c_str()
        );

        station.logged_state = station.state;
        station.logged_state_start_sec = video_time_sec;
    }
}

static void flushFinalStationStates(double video_time_sec)
{
    string shift_timings = getCurrentShiftTimings();

    for (auto& station : g_stations)
    {
        double duration_sec = video_time_sec - station.logged_state_start_sec;

        if (duration_sec <= 0.0)
        {
            continue;
        }

        db_log_station_state(
            station.name.c_str(),
            stationStateName(station.state).c_str(),
            duration_sec,
            shift_timings.c_str()
        );
    }
}


// ============================================================
// DRAWING
// ============================================================

static void drawStaticROI(Mat& frame, const vector<Point>& roi, const Scalar& color, const string& label)
{
    if (roi.empty())
    {
        return;
    }

    polylines(frame, roi, true, color, 3);

    putText(
        frame,
        label,
        roi[0] + Point(0, -10),
        FONT_HERSHEY_SIMPLEX,
        0.7,
        color,
        2
    );
}

static void drawUnitsProduced(Mat& frame, const vector<Point>& roi)
{
    if (roi.empty())
    {
        return;
    }

    string units_text = "UNITS: " + to_string(g_units_produced);
    Point anchor = roi[0] + Point(0, -35);

    int baseline = 0;
    Size ts = getTextSize(units_text, FONT_HERSHEY_SIMPLEX, 0.9, 2, &baseline);

    rectangle(
        frame,
        anchor + Point(-4, 8),
        anchor + Point(ts.width + 4, -ts.height - 8),
        Scalar(0, 0, 0),
        FILLED
    );

    putText(
        frame,
        units_text,
        anchor,
        FONT_HERSHEY_SIMPLEX,
        0.9,
        Scalar(0, 255, 255),
        2
    );
}

static void drawTowels(Mat& frame, const vector<STrack>& towel_stracks)
{
    for (const STrack& t : towel_stracks)
    {
        const vector<float>& tlwh = t.tlwh;

        Rect box((int)tlwh[0], (int)tlwh[1], (int)tlwh[2], (int)tlwh[3]);
        box &= Rect(0, 0, frame.cols, frame.rows);

        if (box.width <= 0 || box.height <= 0)
        {
            continue;
        }

        bool counted = g_counted_towel_ids.count(t.track_id) > 0;
        Scalar tcolor = counted ? Scalar(0, 200, 0) : Scalar(0, 165, 255);

        rectangle(frame, box, tcolor, 2);

        putText(
            frame,
            "TOWEL " + to_string(t.track_id),
            Point(box.x, max(20, box.y - 8)),
            FONT_HERSHEY_SIMPLEX,
            0.6,
            tcolor,
            2
        );
    }
}

static void drawStationROIs(Mat& frame)
{
    for (auto& station : g_stations)
    {
        polylines(frame, station.roi, true, station.color, 3);

        putText(
            frame,
            station.name,
            station.roi[0] + Point(0, -10),
            FONT_HERSHEY_SIMPLEX,
            0.6,
            station.color,
            2
        );
    }
}

static void drawStationTimerBar(Mat& frame)
{
    if (g_stations.empty())
    {
        return;
    }

    const int margin  = 10;
    const int bar_top = 10;
    const int panel_h = 92;

    int usable_w = frame.cols - 2 * margin;
    int n = (int)g_stations.size();
    int panel_w = usable_w / n;

    Mat overlay = frame.clone();

    rectangle(
        overlay,
        Point(margin, bar_top),
        Point(margin + usable_w, bar_top + panel_h),
        Scalar(0, 0, 0),
        FILLED
    );

    addWeighted(overlay, 0.55, frame, 0.45, 0, frame);

    for (int i = 0; i < n; i++)
    {
        Station& station = g_stations[i];

        int x0 = margin + i * panel_w;
        Point origin(x0 + 8, bar_top + 18);

        putText(frame, station.name, origin,
            FONT_HERSHEY_SIMPLEX, 0.45, station.color, 1);

        string state_text = "[" + stationDisplayStateText(station) + "]";

        putText(frame, state_text, origin + Point(0, 18),
            FONT_HERSHEY_SIMPLEX, 0.5, station.color, 2);

        string active_line = "A " + formatHHMMSS(station.active_ms);
        string idle_line   = "I " + formatHHMMSS(station.idle_ms);
        string away_line   = "W " + formatHHMMSS(station.away_ms);

        putText(frame, active_line, origin + Point(0, 38),
            FONT_HERSHEY_SIMPLEX, 0.42, station.color, 1);
        putText(frame, idle_line, origin + Point(0, 55),
            FONT_HERSHEY_SIMPLEX, 0.42, station.color, 1);
        putText(frame, away_line, origin + Point(0, 72),
            FONT_HERSHEY_SIMPLEX, 0.42, station.color, 1);

        if (i > 0)
        {
            line(frame, Point(x0, bar_top), Point(x0, bar_top + panel_h),
                Scalar(80, 80, 80), 1);
        }
    }
}

static void drawTrackPose(Mat& frame, const Track& track)
{
    static const vector<pair<int, int>> skeleton =
    {
        {5, 6}, {5, 7}, {7, 9}, {6, 8}, {8, 10}
    };

    for (auto& conn : skeleton)
    {
        int a = conn.first;
        int b = conn.second;

        if (!track.ema_valid[a] || !track.ema_valid[b])
        {
            continue;
        }

        Point p1((int)track.ema_point[a].x, (int)track.ema_point[a].y);
        Point p2((int)track.ema_point[b].x, (int)track.ema_point[b].y);

        line(frame, p1, p2, Scalar(255, 255, 0), 2);
    }

    auto drawJoint = [&](int idx, Scalar color, int radius)
    {
        if (!track.ema_valid[idx])
        {
            return;
        }

        Point p((int)track.ema_point[idx].x, (int)track.ema_point[idx].y);

        circle(frame, p, radius, color, -1);
        circle(frame, p, radius + 1, Scalar(255, 255, 255), 1);
    };

    static const Scalar LEFT_COLOR(0, 255, 0);
    static const Scalar RIGHT_COLOR(255, 0, 0);
    static const int SHOULDER_ELBOW_RADIUS = 3;
    static const int WRIST_RADIUS          = 5;

    drawJoint(LEFT_SHOULDER, LEFT_COLOR, SHOULDER_ELBOW_RADIUS);
    drawJoint(RIGHT_SHOULDER, RIGHT_COLOR, SHOULDER_ELBOW_RADIUS);
    drawJoint(LEFT_ELBOW, LEFT_COLOR, SHOULDER_ELBOW_RADIUS);
    drawJoint(RIGHT_ELBOW, RIGHT_COLOR, SHOULDER_ELBOW_RADIUS);
    drawJoint(LEFT_WRIST, LEFT_COLOR, WRIST_RADIUS);
    drawJoint(RIGHT_WRIST, RIGHT_COLOR, WRIST_RADIUS);
}

// Small on-frame overlay, top-right corner.
static void drawCurrentShiftBanner(Mat& frame)
{
    string shift_name = getCurrentShiftName();
    string text = "SHIFT: " + (shift_name.empty() ? string("UNKNOWN") : shift_name);

    int baseline = 0;
    Size ts = getTextSize(text, FONT_HERSHEY_SIMPLEX, 0.6, 2, &baseline);

    Point anchor(frame.cols - ts.width - 20, 30);

    rectangle(
        frame,
        anchor + Point(-8, -20),
        anchor + Point(ts.width + 8, 10),
        Scalar(0, 0, 0),
        FILLED
    );

    putText(
        frame,
        text,
        anchor,
        FONT_HERSHEY_SIMPLEX,
        0.6,
        Scalar(255, 255, 255),
        2
    );
}


// ============================================================
// LETTERBOX
// ============================================================

static Mat letterbox(
    const Mat& image,
    int target_size,
    float& scale,
    int& pad_x,
    int& pad_y)
{
    int original_width = image.cols;
    int original_height = image.rows;

    scale = min(
        (float)target_size / original_width,
        (float)target_size / original_height
    );

    int new_width = (int)round(original_width * scale);
    int new_height = (int)round(original_height * scale);

    Mat resized;
    resize(image, resized, Size(new_width, new_height));

    pad_x = (target_size - new_width) / 2;
    pad_y = (target_size - new_height) / 2;

    Mat output(target_size, target_size, CV_8UC3, Scalar(114, 114, 114));
    resized.copyTo(output(Rect(pad_x, pad_y, new_width, new_height)));

    return output;
}


// ============================================================
// YOLO PERSON DETECTION
// ============================================================

static vector<Object> detectPersons(
    Ort::Session& session,
    Ort::AllocatorWithDefaultOptions& allocator,
    const Mat& frame,
    double& inference_ms)
{
    inference_ms = 0.0;

    float scale;
    int pad_x;
    int pad_y;

    Mat input = letterbox(frame, PERSON_INPUT_SIZE, scale, pad_x, pad_y);

    Mat rgb;
    cvtColor(input, rgb, COLOR_BGR2RGB);

    const int channel_size = PERSON_INPUT_SIZE * PERSON_INPUT_SIZE;

    vector<float> input_tensor_values(1 * 3 * PERSON_INPUT_SIZE * PERSON_INPUT_SIZE);

    for (int y = 0; y < PERSON_INPUT_SIZE; y++)
    {
        for (int x = 0; x < PERSON_INPUT_SIZE; x++)
        {
            Vec3b pixel = rgb.at<Vec3b>(y, x);
            int index = y * PERSON_INPUT_SIZE + x;

            input_tensor_values[index] = pixel[0] / 255.0f;
            input_tensor_values[channel_size + index] = pixel[1] / 255.0f;
            input_tensor_values[2 * channel_size + index] = pixel[2] / 255.0f;
        }
    }

    auto input_name_alloc = session.GetInputNameAllocated(0, allocator);
    auto output_name_alloc = session.GetOutputNameAllocated(0, allocator);

    const char* input_name = input_name_alloc.get();
    const char* output_name = output_name_alloc.get();

    vector<int64_t> input_shape = { 1, 3, PERSON_INPUT_SIZE, PERSON_INPUT_SIZE };

    Ort::MemoryInfo memory_info = Ort::MemoryInfo::CreateCpu(OrtArenaAllocator, OrtMemTypeDefault);

    Ort::Value input_tensor = Ort::Value::CreateTensor<float>(
        memory_info,
        input_tensor_values.data(),
        input_tensor_values.size(),
        input_shape.data(),
        input_shape.size()
    );

    auto inference_start = chrono::high_resolution_clock::now();

    const char* input_names[] = { input_name };
    const char* output_names[] = { output_name };

    auto output_tensors = session.Run(
        Ort::RunOptions{ nullptr },
        input_names, &input_tensor, 1,
        output_names, 1
    );

    auto inference_end = chrono::high_resolution_clock::now();

    inference_ms = chrono::duration<double, milli>(inference_end - inference_start).count();

    float* output = output_tensors[0].GetTensorMutableData<float>();

    const int NUM_PREDICTIONS = 8400;

    vector<Rect> boxes;
    vector<float> confidences;

    for (int i = 0; i < NUM_PREDICTIONS; i++)
    {
        float cx = output[0 * NUM_PREDICTIONS + i];
        float cy = output[1 * NUM_PREDICTIONS + i];
        float w  = output[2 * NUM_PREDICTIONS + i];
        float h  = output[3 * NUM_PREDICTIONS + i];
        float person_conf = output[(4 + PERSON_CLASS_ID) * NUM_PREDICTIONS + i];

        if (person_conf < PERSON_CONF_THRESHOLD)
        {
            continue;
        }

        float x1 = cx - w / 2.0f;
        float y1 = cy - h / 2.0f;
        float x2 = cx + w / 2.0f;
        float y2 = cy + h / 2.0f;

        x1 = (x1 - pad_x) / scale;
        y1 = (y1 - pad_y) / scale;
        x2 = (x2 - pad_x) / scale;
        y2 = (y2 - pad_y) / scale;

        x1 = max(0.0f, min(x1, (float)frame.cols));
        y1 = max(0.0f, min(y1, (float)frame.rows));
        x2 = max(0.0f, min(x2, (float)frame.cols));
        y2 = max(0.0f, min(y2, (float)frame.rows));

        Rect box((int)x1, (int)y1, (int)(x2 - x1), (int)(y2 - y1));

        if (box.width <= 0 || box.height <= 0)
        {
            continue;
        }

        boxes.push_back(box);
        confidences.push_back(person_conf);
    }

    vector<int> indices;
    cv::dnn::NMSBoxes(boxes, confidences, PERSON_CONF_THRESHOLD, NMS_THRESHOLD, indices);

    vector<Object> objects;

    for (int index : indices)
    {
        Object obj;
        obj.rect.x      = (float)boxes[index].x;
        obj.rect.y      = (float)boxes[index].y;
        obj.rect.width  = (float)boxes[index].width;
        obj.rect.height = (float)boxes[index].height;
        obj.label       = PERSON_CLASS_ID;
        obj.prob        = confidences[index];

        objects.push_back(obj);
    }

    return objects;
}


// ============================================================
// YOLO TOWEL DETECTION
// ============================================================

static vector<Object> detectTowels(
    Ort::Session& session,
    Ort::AllocatorWithDefaultOptions& allocator,
    const Mat& frame,
    double& inference_ms)
{
    inference_ms = 0.0;

    float scale;
    int pad_x;
    int pad_y;

    Mat input = letterbox(frame, TOWEL_INPUT_SIZE, scale, pad_x, pad_y);

    Mat rgb;
    cvtColor(input, rgb, COLOR_BGR2RGB);

    const int channel_size = TOWEL_INPUT_SIZE * TOWEL_INPUT_SIZE;

    vector<float> input_tensor_values(1 * 3 * TOWEL_INPUT_SIZE * TOWEL_INPUT_SIZE);

    for (int y = 0; y < TOWEL_INPUT_SIZE; y++)
    {
        for (int x = 0; x < TOWEL_INPUT_SIZE; x++)
        {
            Vec3b pixel = rgb.at<Vec3b>(y, x);
            int index = y * TOWEL_INPUT_SIZE + x;

            input_tensor_values[index] = pixel[0] / 255.0f;
            input_tensor_values[channel_size + index] = pixel[1] / 255.0f;
            input_tensor_values[2 * channel_size + index] = pixel[2] / 255.0f;
        }
    }

    auto input_name_alloc  = session.GetInputNameAllocated(0, allocator);
    auto output_name_alloc = session.GetOutputNameAllocated(0, allocator);

    const char* input_name  = input_name_alloc.get();
    const char* output_name = output_name_alloc.get();

    vector<int64_t> input_shape = { 1, 3, TOWEL_INPUT_SIZE, TOWEL_INPUT_SIZE };

    Ort::MemoryInfo memory_info = Ort::MemoryInfo::CreateCpu(OrtArenaAllocator, OrtMemTypeDefault);

    Ort::Value input_tensor = Ort::Value::CreateTensor<float>(
        memory_info,
        input_tensor_values.data(),
        input_tensor_values.size(),
        input_shape.data(),
        input_shape.size()
    );

    auto inference_start = chrono::high_resolution_clock::now();

    const char* input_names[]  = { input_name };
    const char* output_names[] = { output_name };

    auto output_tensors = session.Run(
        Ort::RunOptions{ nullptr },
        input_names, &input_tensor, 1,
        output_names, 1
    );

    auto inference_end = chrono::high_resolution_clock::now();

    inference_ms = chrono::duration<double, milli>(inference_end - inference_start).count();

    float* output = output_tensors[0].GetTensorMutableData<float>();

    const int NUM_PREDICTIONS = 8400;

    vector<Rect> boxes;
    vector<float> confidences;

    for (int i = 0; i < NUM_PREDICTIONS; i++)
    {
        float cx = output[0 * NUM_PREDICTIONS + i];
        float cy = output[1 * NUM_PREDICTIONS + i];
        float w  = output[2 * NUM_PREDICTIONS + i];
        float h  = output[3 * NUM_PREDICTIONS + i];
        float towel_conf = output[(4 + TOWEL_CLASS_ID) * NUM_PREDICTIONS + i];

        if (towel_conf < TOWEL_CONF_THRESHOLD)
        {
            continue;
        }

        float x1 = cx - w / 2.0f;
        float y1 = cy - h / 2.0f;
        float x2 = cx + w / 2.0f;
        float y2 = cy + h / 2.0f;

        x1 = (x1 - pad_x) / scale;
        y1 = (y1 - pad_y) / scale;
        x2 = (x2 - pad_x) / scale;
        y2 = (y2 - pad_y) / scale;

        x1 = max(0.0f, min(x1, (float)frame.cols));
        y1 = max(0.0f, min(y1, (float)frame.rows));
        x2 = max(0.0f, min(x2, (float)frame.cols));
        y2 = max(0.0f, min(y2, (float)frame.rows));

        Rect box((int)x1, (int)y1, (int)(x2 - x1), (int)(y2 - y1));

        if (box.width <= 0 || box.height <= 0)
        {
            continue;
        }

        boxes.push_back(box);
        confidences.push_back(towel_conf);
    }

    vector<int> indices;
    cv::dnn::NMSBoxes(boxes, confidences, TOWEL_CONF_THRESHOLD, NMS_THRESHOLD, indices);

    vector<Object> objects;

    for (int index : indices)
    {
        Object obj;
        obj.rect.x      = (float)boxes[index].x;
        obj.rect.y      = (float)boxes[index].y;
        obj.rect.width  = (float)boxes[index].width;
        obj.rect.height = (float)boxes[index].height;
        obj.label       = TOWEL_CLASS_ID;
        obj.prob        = confidences[index];

        objects.push_back(obj);
    }

    return objects;
}


static vector<Detection> objectsToDetections(const vector<Object>& objects, const Mat& frame)
{
    vector<Detection> dets;
    dets.reserve(objects.size());

    for (const Object& obj : objects)
    {
        Rect box((int)obj.rect.x, (int)obj.rect.y, (int)obj.rect.width, (int)obj.rect.height);
        box &= Rect(0, 0, frame.cols, frame.rows);

        Detection d;
        d.box = box;
        d.confidence = obj.prob;

        dets.push_back(d);
    }

    return dets;
}


static void preparePoseInput(
    const Mat& person_crop,
    vector<float>& destination,
    size_t batch_index)
{
    float scale;
    int pad_x;
    int pad_y;

    Mat input = letterbox(person_crop, POSE_INPUT_SIZE, scale, pad_x, pad_y);

    Mat rgb;
    cvtColor(input, rgb, COLOR_BGR2RGB);

    const int channel_size = POSE_INPUT_SIZE * POSE_INPUT_SIZE;
    const size_t batch_offset = batch_index * 3 * channel_size;

    for (int y = 0; y < POSE_INPUT_SIZE; y++)
    {
        for (int x = 0; x < POSE_INPUT_SIZE; x++)
        {
            Vec3b pixel = rgb.at<Vec3b>(y, x);
            int index = y * POSE_INPUT_SIZE + x;

            destination[batch_offset + index] = pixel[0] / 255.0f;
            destination[batch_offset + channel_size + index] = pixel[1] / 255.0f;
            destination[batch_offset + 2 * channel_size + index] = pixel[2] / 255.0f;
        }
    }
}


static vector<PersonPose> estimatePosesBatch(
    Ort::Session& session,
    Ort::AllocatorWithDefaultOptions& allocator,
    const Mat& frame,
    const vector<Detection>& persons,
    double& inference_ms)
{
    inference_ms = 0.0;

    vector<PersonPose> poses;

    const size_t batch_size = persons.size();

    if (batch_size == 0)
    {
        return poses;
    }

    poses.resize(batch_size);

    for (size_t i = 0; i < batch_size; i++)
    {
        poses[i].keypoints.resize(NUM_KEYPOINTS);

        for (auto& kp : poses[i].keypoints)
        {
            kp.point = Point2f(-1, -1);
            kp.confidence = 0.0f;
            kp.valid = false;
        }
    }

    const int channel_size = POSE_INPUT_SIZE * POSE_INPUT_SIZE;
    const size_t image_size = 3 * channel_size;

    vector<float> input_tensor_values(batch_size * image_size);

    for (size_t i = 0; i < batch_size; i++)
    {
        Rect box = persons[i].box;
        box &= Rect(0, 0, frame.cols, frame.rows);

        if (box.width <= 0 || box.height <= 0)
        {
            continue;
        }

        Mat person_crop = frame(box).clone();

        preparePoseInput(person_crop, input_tensor_values, i);
    }

    auto input_name_alloc = session.GetInputNameAllocated(0, allocator);
    auto output_name_alloc = session.GetOutputNameAllocated(0, allocator);

    const char* input_name = input_name_alloc.get();
    const char* output_name = output_name_alloc.get();

    vector<int64_t> input_shape = { (int64_t)batch_size, 3, POSE_INPUT_SIZE, POSE_INPUT_SIZE };

    Ort::MemoryInfo memory_info = Ort::MemoryInfo::CreateCpu(OrtArenaAllocator, OrtMemTypeDefault);

    Ort::Value input_tensor = Ort::Value::CreateTensor<float>(
        memory_info,
        input_tensor_values.data(),
        input_tensor_values.size(),
        input_shape.data(),
        input_shape.size()
    );

    const char* input_names[] = { input_name };
    const char* output_names[] = { output_name };

    auto inference_start = chrono::high_resolution_clock::now();

    auto output_tensors = session.Run(
        Ort::RunOptions{ nullptr },
        input_names, &input_tensor, 1,
        output_names, 1
    );

    auto inference_end = chrono::high_resolution_clock::now();

    inference_ms = chrono::duration<double, milli>(inference_end - inference_start).count();

    float* output = output_tensors[0].GetTensorMutableData<float>();

    const int NUM_PREDICTIONS = 8400;
    const int NUM_CHANNELS = 56; // 17 keypoints * 3 (x,y,conf) + 5 (box + conf)

    const size_t output_per_person = NUM_CHANNELS * NUM_PREDICTIONS;

    for (size_t person_index = 0; person_index < batch_size; person_index++)
    {
        float* person_output = output + person_index * output_per_person;

        int best_index = -1;
        float best_confidence = 0.0f;

        for (int i = 0; i < NUM_PREDICTIONS; i++)
        {
            float confidence = person_output[4 * NUM_PREDICTIONS + i];

            if (confidence > best_confidence)
            {
                best_confidence = confidence;
                best_index = i;
            }
        }

        if (best_index < 0 || best_confidence < POSE_CONF_THRESHOLD)
        {
            continue;
        }

        Rect person_box = persons[person_index].box;

        for (int k : TRACKED_KEYPOINTS)
        {
            int base = (5 + k * 3) * NUM_PREDICTIONS + best_index;

            float x = person_output[base];
            float y = person_output[base + NUM_PREDICTIONS];
            float confidence = person_output[base + 2 * NUM_PREDICTIONS];

            if (confidence < POSE_CONF_THRESHOLD)
            {
                continue;
            }

            float crop_width = (float)person_box.width;
            float crop_height = (float)person_box.height;

            float scale = min(
                (float)POSE_INPUT_SIZE / crop_width,
                (float)POSE_INPUT_SIZE / crop_height
            );

            int new_width = (int)round(crop_width * scale);
            int new_height = (int)round(crop_height * scale);

            int pad_x = (POSE_INPUT_SIZE - new_width) / 2;
            int pad_y = (POSE_INPUT_SIZE - new_height) / 2;

            float crop_x = (x - pad_x) / scale;
            float crop_y = (y - pad_y) / scale;

            float frame_x = person_box.x + crop_x;
            float frame_y = person_box.y + crop_y;

            frame_x = max((float)person_box.x, min(frame_x, (float)(person_box.x + person_box.width)));
            frame_y = max((float)person_box.y, min(frame_y, (float)(person_box.y + person_box.height)));

            poses[person_index].keypoints[k].point = Point2f(frame_x, frame_y);
            poses[person_index].keypoints[k].confidence = confidence;
            poses[person_index].keypoints[k].valid = true;
        }
    }

    return poses;
}


// ============================================================
// applyConfigToRuntime
// ============================================================

static void applyConfigToRuntime()
{
    PERSON_INPUT_SIZE     = g_cfg.person_input_size;
    PERSON_CONF_THRESHOLD = g_cfg.person_conf_threshold;
    NMS_THRESHOLD         = g_cfg.nms_threshold;
    PERSON_CLASS_ID       = g_cfg.person_class_id;

    TOWEL_INPUT_SIZE     = g_cfg.towel_input_size;
    TOWEL_CONF_THRESHOLD = g_cfg.towel_conf_threshold;
    TOWEL_CLASS_ID       = g_cfg.towel_class_id;

    POSE_INPUT_SIZE     = g_cfg.pose_input_size;
    POSE_CONF_THRESHOLD = g_cfg.pose_conf_threshold;

    MIN_TRACK_BOX_AREA           = g_cfg.min_track_box_area;
    ROI_PERSON_OVERLAP_THRESHOLD = g_cfg.roi_person_overlap_threshold;

    g_conveyor_belt_roi.clear();
    for (int i = 0; i < g_cfg.conveyor_belt_roi_count; i++)
    {
        g_conveyor_belt_roi.push_back(
            Point(g_cfg.conveyor_belt_roi[i].x, g_cfg.conveyor_belt_roi[i].y)
        );
    }

    TOWEL_LINE_P1 = Point2f((float)g_cfg.towel_line_p1.x, (float)g_cfg.towel_line_p1.y);
    TOWEL_LINE_P2 = Point2f((float)g_cfg.towel_line_p2.x, (float)g_cfg.towel_line_p2.y);
    TOWEL_LINE_BRIDGE_MAX_GAP_SEC      = g_cfg.towel_line_bridge_max_gap_sec;
    TOWEL_LINE_PROXIMITY_PX            = g_cfg.towel_line_proximity_px;
    TOWEL_LINE_TRACK_MAX_MISSED_FRAMES = g_cfg.towel_line_track_max_missed_frames;

    initTowelLine();
}


// ============================================================
// RTSP CAPTURE THREAD
// ============================================================
//
// Runs cv::VideoCapture::read() on its own thread and keeps only the
// newest frame, so slow inference never builds up a decode backlog.
// Reconnect-on-stall lives inside run().
// ============================================================

class RtspFrameGrabber
{
public:
    ~RtspFrameGrabber()
    {
        stop();
    }

    void start(const string& url)
    {
        url_ = url;
        running_ = true;
        thread_ = std::thread(&RtspFrameGrabber::run, this);
    }

    void stop()
    {
        if (!running_.exchange(false))
        {
            return;
        }

        frame_cv_.notify_all();
        connect_cv_.notify_all();

        if (thread_.joinable())
        {
            thread_.join();
        }
    }

    bool waitUntilConnected(int& width, int& height, double& fps)
    {
        std::unique_lock<std::mutex> lock(connect_mutex_);

        connect_cv_.wait(lock, [this]
        {
            return connected_ || !running_ || g_stop_requested;
        });

        if (!connected_)
        {
            return false;
        }

        width  = width_;
        height = height_;
        fps    = fps_;
        return true;
    }

    bool getLatestFrame(Mat& out)
    {
        std::unique_lock<std::mutex> lock(frame_mutex_);

        frame_cv_.wait(lock, [this]
        {
            return has_new_frame_ || !running_ || g_stop_requested;
        });

        if (!has_new_frame_)
        {
            return false;
        }

        out = latest_frame_;
        has_new_frame_ = false;
        return true;
    }

private:
    void run()
    {
        static const long long MAX_CONSECUTIVE_EMPTY_FRAMES = 300; // ~10s at 30fps

        while (running_ && !g_stop_requested)
        {
            cap_.open(url_, CAP_FFMPEG);
            cap_.set(CAP_PROP_BUFFERSIZE, 1);

            if (!cap_.isOpened())
            {
                cerr << "RtspFrameGrabber: could not open " << url_
                     << " -- retrying in 2s." << endl;

                for (int waited_ms = 0; waited_ms < 2000 && running_ && !g_stop_requested; waited_ms += 100)
                {
                    std::this_thread::sleep_for(std::chrono::milliseconds(100));
                }

                continue;
            }

            {
                int w = (int)cap_.get(CAP_PROP_FRAME_WIDTH);
                int h = (int)cap_.get(CAP_PROP_FRAME_HEIGHT);
                double f = cap_.get(CAP_PROP_FPS);

                if (f <= 0.0)
                {
                    f = 30.0;
                }

                {
                    std::lock_guard<std::mutex> lock(connect_mutex_);
                    width_ = w;
                    height_ = h;
                    fps_ = f;
                    connected_ = true;
                }
                connect_cv_.notify_all();
            }

            long long consecutive_empty_frames = 0;

            while (running_ && !g_stop_requested)
            {
                Mat frame;
                cap_ >> frame;

                if (frame.empty())
                {
                    consecutive_empty_frames++;

                    if (consecutive_empty_frames >= MAX_CONSECUTIVE_EMPTY_FRAMES)
                    {
                        cerr << "RtspFrameGrabber: " << consecutive_empty_frames
                             << " consecutive empty frames from " << url_
                             << " -- reconnecting." << endl;
                        break;
                    }

                    continue;
                }

                consecutive_empty_frames = 0;

                {
                    std::lock_guard<std::mutex> lock(frame_mutex_);
                    latest_frame_ = frame;
                    has_new_frame_ = true;
                }
                frame_cv_.notify_one();
            }

            cap_.release();
        }

        frame_cv_.notify_all();
        connect_cv_.notify_all();
    }

    string url_;
    VideoCapture cap_;
    std::thread thread_;
    std::atomic<bool> running_{false};

    std::mutex connect_mutex_;
    std::condition_variable connect_cv_;
    bool connected_ = false;
    int width_ = 0;
    int height_ = 0;
    double fps_ = 30.0;

    std::mutex frame_mutex_;
    std::condition_variable frame_cv_;
    Mat latest_frame_;
    bool has_new_frame_ = false;
};


// ============================================================
// LIVE TERMINAL STATUS
// ============================================================

static void printLiveStatus(long long frame_number, long long total_frames)
{
    cout << "\rFrame: " << frame_number;

    if (total_frames > 0)
    {
        double progress =
            100.0 * (double)frame_number / (double)total_frames;

        cout << " / " << total_frames
             << " (" << fixed << setprecision(1)
             << progress << "%)";
    }

    cout << " | Units: " << g_units_produced;

    for (const auto& station : g_stations)
    {
        cout << " | "
             << station.name
             << ": "
             << stationDisplayStateText(station);
    }

    cout << flush;
}


// ============================================================
// DETECTION PIPELINE  (runs on the ctpat thread)
// ============================================================

static void ctpatRun()
{
    applyConfigToRuntime();

    string person_model = g_cfg.person_model;
    string pose_model   = g_cfg.pose_model;
    string towel_model  = g_cfg.towel_model;
    const char* output_video = g_cfg.output_video_path;

    ofstream frame_log(g_cfg.frame_log_path);

    if (!frame_log.is_open())
    {
        cerr << "ERROR: Could not open " << g_cfg.frame_log_path << " for writing." << endl;
        return;
    }

    frame_log << "Frame | YOLOv8m (ms) | Pose (ms) | Towel (ms) | Total Inference (ms)\n";
    frame_log << "----------------------------------------------------------\n";

    // --------------------------------------------------------
    // ONNX Runtime setup (CUDA if available, CPU fallback)
    // --------------------------------------------------------

    Ort::Env env(ORT_LOGGING_LEVEL_WARNING, "PersonTracking");

    Ort::SessionOptions session_options;
    session_options.SetIntraOpNumThreads(4);
    session_options.SetGraphOptimizationLevel(GraphOptimizationLevel::ORT_ENABLE_ALL);

    bool cuda_enabled = false;

    try
    {
        OrtCUDAProviderOptions cuda_options{};
        cuda_options.device_id = 0;
        cuda_options.arena_extend_strategy = 1;
        cuda_options.gpu_mem_limit = SIZE_MAX;

        session_options.AppendExecutionProvider_CUDA(cuda_options);
        cuda_enabled = true;
        cout << "CUDA execution provider enabled (device 0)." << endl;
    }
    catch (const Ort::Exception& e)
    {
        cerr << "WARNING: Could not enable CUDA execution provider ("
             << e.what() << "). Falling back to CPU." << endl;
    }

    if (!cuda_enabled)
    {
        cout << "Running on CPU." << endl;
    }

    cout << "Loading YOLOv8 person detector: " << person_model << endl;
    Ort::Session person_session(env, person_model.c_str(), session_options);

    cout << "Loading YOLOv8 pose model: " << pose_model << endl;
    Ort::Session pose_session(env, pose_model.c_str(), session_options);

    cout << "Loading YOLOv8 towel detector: " << towel_model << endl;
    Ort::Session towel_session(env, towel_model.c_str(), session_options);

    Ort::AllocatorWithDefaultOptions allocator;

    try
    {
        auto pose_input_info = pose_session.GetInputTypeInfo(0);
        auto pose_tensor_info = pose_input_info.GetTensorTypeAndShapeInfo();
        vector<int64_t> pose_shape = pose_tensor_info.GetShape();

        cout << "Pose model input shape: ";

        for (size_t i = 0; i < pose_shape.size(); i++)
        {
            cout << pose_shape[i];

            if (i + 1 < pose_shape.size())
            {
                cout << " x ";
            }
        }

        cout << endl;

        if (pose_shape.size() == 4 && pose_shape[0] == 1)
        {
            cerr << endl
                 << "WARNING:" << endl
                 << "Pose ONNX model appears to have a fixed batch size of 1." << endl
                 << "The batched pose code requires a dynamic batch dimension." << endl
                 << "Re-export the pose model with dynamic batch support." << endl
                 << endl;
        }
    }
    catch (const Ort::Exception& e)
    {
        cerr << "WARNING: Could not inspect pose model input shape: " << e.what() << endl;
    }

    // --------------------------------------------------------
    // RTSP capture
    // --------------------------------------------------------

    cout << "Connecting to RTSP stream: " << g_cfg.rtsp_url << endl;

    RtspFrameGrabber grabber;
    grabber.start(g_cfg.rtsp_url);

    int frame_width  = 0;
    int frame_height = 0;
    double fps = 30.0;

    if (!grabber.waitUntilConnected(frame_width, frame_height, fps))
    {
        if (g_stop_requested)
        {
            cout << "SIGINT received while connecting -- exiting." << endl;
        }
        else
        {
            cerr << "ERROR: Could not connect to RTSP stream: " << g_cfg.rtsp_url << endl;
        }

        grabber.stop();
        return;
    }

    long long total_frames = 0;

    cout << "Video resolution: " << frame_width << " x " << frame_height << endl;
    cout << "FPS: " << fps << endl;
    cout << "Person input size: " << PERSON_INPUT_SIZE << " x " << PERSON_INPUT_SIZE << endl;
    cout << "Pose input size: " << POSE_INPUT_SIZE << " x " << POSE_INPUT_SIZE << endl;
    cout << "Towel input size: " << TOWEL_INPUT_SIZE << " x " << TOWEL_INPUT_SIZE << endl;

    int fourcc = VideoWriter::fourcc('m', 'p', '4', 'v');
    VideoWriter writer;

    if (g_cfg.save_output_video)
    {
        writer.open(output_video, fourcc, fps, Size(frame_width, frame_height));

        if (!writer.isOpened())
        {
            cerr << "ERROR: Could not create output video: " << output_video << endl;
            grabber.stop();
            return;
        }

        cout << "Output video: " << output_video << endl;
        cout << "(Press Ctrl+C to stop - the video will be saved up to the last processed frame.)" << endl;
    }
    else
    {
        cout << "Output video saving is OFF (config: save_output_video = false) -- no video file will be written." << endl;
    }

    cout << endl;

    buildStationsFromConfig();
    computeGlobalTrackingParams();

    cout << "Active line: " << g_cfg.active_line
         << " (" << g_stations.size() << " station(s))" << endl;
    cout << "Shifts loaded: " << g_cfg.shift_count;

    if (g_cfg.shift_count > 0)
    {
        cout << " (";
        for (int i = 0; i < g_cfg.shift_count; i++)
        {
            cout << g_cfg.shifts[i].shift_name;
            if (i + 1 < g_cfg.shift_count) cout << ", ";
        }
        cout << ")";
    }

    cout << " -- current shift: ";
    {
        string shift_name = getCurrentShiftName();
        cout << (shift_name.empty() ? "UNKNOWN" : shift_name);
    }
    cout << endl;

    // --------------------------------------------------------
    // ByteTrack -- separate trackers for persons and towels
    // --------------------------------------------------------

    BYTETracker tracker((int)round(fps), 30);
    BYTETracker towel_tracker((int)round(fps), 30);

    // --------------------------------------------------------
    // Main loop
    // --------------------------------------------------------

    Mat frame;
    long long frame_number = 0;

    double total_person_inference_ms = 0.0;
    double total_pose_inference_ms = 0.0;
    double total_towel_inference_ms = 0.0;
    long long person_inference_count = 0;
    long long towel_inference_count = 0;
    long long pose_batch_count = 0;
    long long total_pose_persons = 0;

    while (true)
    {
        if (g_stop_requested)
        {
            cout << endl << "Stop requested - stopping after frame "
                 << frame_number << ". Finalizing output video..." << endl;
            break;
        }

        if (!grabber.getLatestFrame(frame))
        {
            if (!g_stop_requested)
            {
                cerr << "ERROR: RTSP grabber stopped unexpectedly -- ending run." << endl;
            }
            break;
        }

        frame_number++;

        static auto last_frame_wall_time = chrono::steady_clock::now();
        static double video_time_sec_accum = 0.0;

        auto now_wall_time = chrono::steady_clock::now();
        double frame_dt_sec = chrono::duration<double>(now_wall_time - last_frame_wall_time).count();
        last_frame_wall_time = now_wall_time;

        if (frame_dt_sec <= 0.0 || frame_dt_sec > 1.0)
        {
            frame_dt_sec = 1.0 / fps;
        }

        video_time_sec_accum += frame_dt_sec;
        double video_time_sec = video_time_sec_accum;

        // ---- Person detection ----

        double person_inference_ms = 0.0;
        vector<Object> objects = detectPersons(person_session, allocator, frame, person_inference_ms);

        total_person_inference_ms += person_inference_ms;
        person_inference_count++;

        // ---- Pose estimation (batched) ----

        vector<Detection> person_dets = objectsToDetections(objects, frame);

        double pose_inference_ms = 0.0;
        vector<PersonPose> raw_poses = estimatePosesBatch(
            pose_session, allocator, frame, person_dets, pose_inference_ms);

        if (!person_dets.empty())
        {
            total_pose_persons += person_dets.size();
            pose_batch_count++;
            total_pose_inference_ms += pose_inference_ms;
        }

        // ---- Towel detection + tracker + unit count ----

        double towel_inference_ms = 0.0;
        vector<Object> towel_objects = detectTowels(towel_session, allocator, frame, towel_inference_ms);

        total_towel_inference_ms += towel_inference_ms;
        towel_inference_count++;

        vector<STrack> towel_stracks = towel_tracker.update(towel_objects);
        updateTowelCount(towel_stracks, video_time_sec);

        // ---- Per-frame inference timing ----

        frame_log << frame_number
                  << " | "
                  << fixed << setprecision(2)
                  << person_inference_ms
                  << " | "
                  << pose_inference_ms
                  << " | "
                  << towel_inference_ms
                  << " | "
                  << (person_inference_ms + pose_inference_ms + towel_inference_ms)
                  << "\n";

        frame_log.flush();

        // ---- ByteTrack (persons) ----

        vector<STrack> output_stracks = tracker.update(objects);

        syncTracksWithByteTrack(output_stracks, person_dets, raw_poses, video_time_sec);
        updateStations(frame_dt_sec);

        logStationStateChanges(video_time_sec);

        // ---- Draw ROIs ----

        drawStaticROI(frame, g_conveyor_belt_roi, Scalar(0, 255, 255), "CONVEYOR BELT");
        drawUnitsProduced(frame, g_conveyor_belt_roi);
        drawTowelLine(frame);
        drawTowels(frame, towel_stracks);
        drawStationROIs(frame);

        // ---- Draw tracked persons + smoothed pose ----

        for (size_t i = 0; i < output_stracks.size(); i++)
        {
            const vector<float>& tlwh = output_stracks[i].tlwh;

            if (tlwh[2] * tlwh[3] < MIN_TRACK_BOX_AREA)
            {
                continue;
            }

            int track_id = output_stracks[i].track_id;
            Scalar color = tracker.get_color(track_id);

            Rect box((int)tlwh[0], (int)tlwh[1], (int)tlwh[2], (int)tlwh[3]);
            box &= Rect(0, 0, frame.cols, frame.rows);

            if (box.width <= 0 || box.height <= 0)
            {
                continue;
            }

            rectangle(frame, box, color, 2);

            string label = "ID " + to_string(track_id);

            putText(
                frame,
                label,
                Point(box.x, max(20, box.y - 8)),
                FONT_HERSHEY_SIMPLEX,
                0.7,
                color,
                2
            );

            auto it = g_tracks.find(track_id);

            if (it != g_tracks.end())
            {
                drawTrackPose(frame, it->second);
            }
        }

        drawStationTimerBar(frame);
        drawCurrentShiftBanner(frame);

        if (g_cfg.save_output_video)
        {
            writer.write(frame);
        }

        printLiveStatus(frame_number, total_frames);
    }

    cout << endl;

    grabber.stop();

    if (g_cfg.save_output_video)
    {
        writer.release();
    }

    frame_log.close();

    // Flush each station's still-open episode (DB is closed by main after join).
    {
        double final_video_time_sec = (fps > 0.0) ? ((double)frame_number / fps) : 0.0;
        flushFinalStationStates(final_video_time_sec);
    }

    cout << endl;
    cout << "============================================" << endl;
    cout << "INFERENCE TIMING SUMMARY" << endl;
    cout << "============================================" << endl;

    if (g_stop_requested)
    {
        cout << "(Stopped early after " << frame_number << " frames)" << endl;
    }

    if (person_inference_count > 0)
    {
        cout << fixed << setprecision(3)
             << "Average person detection inference: "
             << (total_person_inference_ms / person_inference_count) << " ms" << endl;
    }

    if (pose_batch_count > 0)
    {
        double average_batch_ms = total_pose_inference_ms / pose_batch_count;

        double average_persons_per_frame =
            (frame_number > 0) ? ((double)total_pose_persons / frame_number) : 0.0;

        cout << fixed << setprecision(3)
             << "Average batched pose inference:      " << average_batch_ms << " ms/frame" << endl;

        cout << fixed << setprecision(2)
             << "Average persons per pose batch:       " << average_persons_per_frame << endl;
    }

    if (towel_inference_count > 0)
    {
        cout << fixed << setprecision(3)
             << "Average towel detection inference:  "
             << (total_towel_inference_ms / towel_inference_count) << " ms" << endl;
    }

    cout << "Frames processed: " << frame_number << endl;
    cout << "Person inference calls: " << person_inference_count << endl;
    cout << "Pose batch inference calls: " << pose_batch_count << endl;
    cout << "Total persons processed by pose: " << total_pose_persons << endl;
    cout << "Towel inference calls: " << towel_inference_count << endl;

    cout << "============================================" << endl;
    cout << "STATION TIMER SUMMARY" << endl;
    cout << "============================================" << endl;

    for (auto& station : g_stations)
    {
        cout << station.name
             << " | ACTIVE " << formatHHMMSS(station.active_ms)
             << " | IDLE "   << formatHHMMSS(station.idle_ms)
             << " | AWAY "   << formatHHMMSS(station.away_ms) << endl;
    }

    cout << "============================================" << endl;
    cout << "CONVEYOR BELT / UNIT COUNT" << endl;
    cout << "============================================" << endl;
    cout << "Units produced (towels): " << g_units_produced << endl;

    cout << "============================================" << endl;
    cout << "Processing complete!" << endl;

    if (g_cfg.save_output_video)
    {
        cout << "Output: " << output_video << endl;
    }
    else
    {
        cout << "Output video was not saved (config: save_output_video = false)." << endl;
    }

    cout << "============================================" << endl;
}


// ============================================================
// THREAD CONTROL  (public API declared in ctpat.h)
// ============================================================

static std::thread       g_ctpat_thread;
static std::atomic<bool> g_ctpat_running{false};

static void ctpatThreadMain()
{
    try
    {
        ctpatRun();
    }
    catch (const std::exception& e)
    {
        cerr << "ctpat thread: unhandled exception: " << e.what() << endl;
    }
    catch (...)
    {
        cerr << "ctpat thread: unknown exception." << endl;
    }

    g_ctpat_running = false;
}

void ctpat_start()
{
    if (g_ctpat_running.exchange(true))
    {
        return; // already running
    }

    g_ctpat_thread = std::thread(ctpatThreadMain);
}

void ctpat_stop()
{
    g_stop_requested = 1;
}

void ctpat_join()
{
    if (g_ctpat_thread.joinable())
    {
        g_ctpat_thread.join();
    }
}

bool ctpat_is_running()
{
    return g_ctpat_running.load();
}