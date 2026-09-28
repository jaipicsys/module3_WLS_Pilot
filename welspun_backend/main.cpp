#include <iostream>
#include <string>
#include <thread>
#include <chrono>
#include <csignal>
#include <ctime>
#include <cstdio>
#include <unistd.h>

#include <microhttpd.h>

#include "ctpat.hpp"
#include "db.h"

extern "C"
{
#include "routes.h"
}

using namespace std;

// ------------------------------------------------------------
// Globals shared with ctpat.cpp (declared extern in ctpat.h)
// ------------------------------------------------------------
AppConfig g_cfg;
volatile sig_atomic_t g_stop_requested = 0;

static void handleSigint(int /*signum*/)
{
    g_stop_requested = 1;
}


// ============================================================
// CURRENT SHIFT LOOKUP
// ============================================================

static bool parseTimingsRange(const char* timings, int& start_min, int& end_min)
{
    int sh = 0, sm = 0, eh = 0, em = 0;

    if (sscanf(timings, "%d:%d - %d:%d", &sh, &sm, &eh, &em) != 4)
    {
        return false;
    }

    start_min = sh * 60 + sm;
    end_min   = eh * 60 + em;
    return true;
}

static int currentMinutesSinceMidnightIST()
{
    time_t now = time(NULL);
    now += 5 * 3600 + 30 * 60; // UTC -> IST, same fixed offset as db.c's ist_now()

    struct tm tm_ist;
    gmtime_r(&now, &tm_ist);

    return tm_ist.tm_hour * 60 + tm_ist.tm_min;
}

static int currentShiftIndex()
{
    int now_min = currentMinutesSinceMidnightIST();

    for (int i = 0; i < g_cfg.shift_count; i++)
    {
        int start_min = 0, end_min = 0;

        if (!parseTimingsRange(g_cfg.shifts[i].timings, start_min, end_min))
        {
            continue;
        }

        if (start_min <= end_min)
        {
            if (now_min >= start_min && now_min < end_min)
            {
                return i;
            }
        }
        else
        {
            // Overnight shift, e.g. 22:00 - 06:00
            if (now_min >= start_min || now_min < end_min)
            {
                return i;
            }
        }
    }

    return -1;
}

string getCurrentShiftName()
{
    int i = currentShiftIndex();
    return (i >= 0) ? g_cfg.shifts[i].shift_name : "";
}

string getCurrentShiftTimings()
{
    int i = currentShiftIndex();
    return (i >= 0) ? g_cfg.shifts[i].timings : "";
}


// ============================================================
// MAIN
// ============================================================

int main(int argc, char* argv[])
{
        // Always run relative to the project root, so config.json and the
    // models/db/output paths inside it resolve no matter where ./towel is launched.
    if (chdir(PROJECT_ROOT) != 0)
    {
        cerr << "ERROR: could not change directory to " << PROJECT_ROOT << endl;
        return -1;
    }
    string config_path = "config.json";

    if (argc >= 2)
    {
        config_path = argv[1];
    }

    cout << "Loading config: " << config_path << endl;

    if (config_load(config_path.c_str(), &g_cfg) != 0)
    {
        cerr << "ERROR: failed to load " << config_path
             << " -- see message above. Usage: " << argv[0]
             << " [path/to/config.json]" << endl;
        return -1;
    }

    signal(SIGINT, handleSigint);

    // --------------------------------------------------------
    // SQLite logging
    // --------------------------------------------------------

    if (db_init(g_cfg.db_path) != 0)
    {
        cerr << "WARNING: could not open " << g_cfg.db_path << " -- continuing without DB logging." << endl;
    }

    // --------------------------------------------------------
    // HTTP API
    // --------------------------------------------------------

    struct MHD_Daemon* api_daemon = MHD_start_daemon(
        MHD_USE_SELECT_INTERNALLY,
        g_cfg.api_port,
        nullptr, nullptr,
        routes_connection_handler,
        nullptr,
        MHD_OPTION_NOTIFY_COMPLETED,
        routes_request_completed,
        nullptr,
        MHD_OPTION_END);

    if (!api_daemon)
    {
        cerr << "WARNING: could not start HTTP API on port " << g_cfg.api_port
             << " -- continuing without it." << endl;
    }
    else
    {
        cout << "HTTP API running on port " << g_cfg.api_port << endl;
    }

    // --------------------------------------------------------
    // Detection thread (ctpat.cpp)
    // --------------------------------------------------------

    ctpat_start();

    // Wait for Ctrl+C, or for the ctpat thread to exit on its own
    // (e.g. RTSP connect failure / model load failure).
    while (!g_stop_requested && ctpat_is_running())
    {
        this_thread::sleep_for(chrono::milliseconds(200));
    }

    if (g_stop_requested)
    {
        cout << endl << "SIGINT received - stopping detection thread..." << endl;
    }

    ctpat_stop();
    ctpat_join();   // ctpat flushes final station states to the DB before returning

    db_close();

    if (api_daemon)
    {
        MHD_stop_daemon(api_daemon);
    }

    cout << "Shutdown complete." << endl;

    return 0;
}