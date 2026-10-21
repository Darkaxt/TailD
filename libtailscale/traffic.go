// Copyright (c) TailD contributors. SPDX-License-Identifier: BSD-3-Clause
package libtailscale

func (a *App) ConfigureTraffic(session string) string { return a.traffic.Configure(session) }
