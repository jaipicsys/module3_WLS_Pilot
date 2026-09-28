#pragma once

#include <string>
#include <csignal>

#include "main_config_utils.h"

// Defined in main.cpp
extern AppConfig g_cfg;
extern volatile sig_atomic_t g_stop_requested;

std::string getCurrentShiftName();
std::string getCurrentShiftTimings();

// Defined in ctpat.cpp
void ctpat_start();            // launches the detection thread
void ctpat_stop();             // requests stop (sets g_stop_requested)
void ctpat_join();             // waits for the thread to exit
bool ctpat_is_running();       // true while the thread is alive