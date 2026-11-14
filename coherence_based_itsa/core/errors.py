# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright (C) 2026 Allen John T. Bautista

class CancelledError(Exception):
    pass


def check_cancel(cancelled):
    if cancelled():
        raise CancelledError("Run cancelled. Partial outputs are retained with cancelled status.")
