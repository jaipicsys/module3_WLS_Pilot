#ifndef ROUTES_H
#define ROUTES_H

/* ============================================================
 * routes.h -- HTTP API layer for ctpat
 *
 * Mirrors the shape of the previous project's routes.h so the
 * dispatcher wired into MHD_start_daemon() in ctpat.cpp looks
 * identical. Everything here is infrastructure only -- no
 * endpoint bodies. Fill those in inside routes.c.
 * ============================================================ */

#include <microhttpd.h>
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C"
{
#endif

/* ------------------------------------------------------------
 * Size limits
 * ------------------------------------------------------------ */
#define ROUTES_BODY_MAX   (8192U)    /* max buffered POST/PUT body            */
#define ROUTES_STR_MAX    (256U)     /* max length of a single JSON field     */
#define ROUTES_RESP_MAX   (16384U)   /* max size of a hand-built JSON reply   */

/* ------------------------------------------------------------
 * Return codes for the small hand-rolled JSON/body parsing
 * helpers in routes.c (json_get_string / json_get_int, etc.)
 * ------------------------------------------------------------ */
#define ROUTES_OK          (0)
#define ROUTES_ERR_PARAM   (-1)

/* ------------------------------------------------------------
 * Entry points wired into MHD_start_daemon() from ctpat.cpp's
 * main(). See the "HTTP API" block added to main() for usage.
 * ------------------------------------------------------------ */
enum MHD_Result routes_connection_handler(
    void *cls,
    struct MHD_Connection *connection,
    const char *url,
    const char *method,
    const char *version,
    const char *upload_data,
    size_t *upload_data_size,
    void **con_cls);

void routes_request_completed(
    void *cls,
    struct MHD_Connection *connection,
    void **con_cls,
    enum MHD_RequestTerminationCode toe);

#ifdef __cplusplus
}
#endif

#endif /* ROUTES_H */