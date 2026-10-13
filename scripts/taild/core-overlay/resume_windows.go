// Copyright (c) Tailscale Inc & contributors
// SPDX-License-Identifier: BSD-3-Clause
package main

import (
	"path/filepath"
	"tailscale.com/util/winutil"
)

// The same inherited original-GUI-user launcher used for the tray starts the
// owner collector after update. It does not open another analytics window.
func platformResumeAnalytics() (installResult, error) {
	manager, service, config, err := openService()
	if err != nil { return installResult{}, err }
	defer manager.Disconnect()
	defer service.Close()
	paths, err := resolveInstallPaths(config.BinaryPathName)
	if err != nil { return installResult{}, err }
	if err := winutil.StartProcessAsCurrentGUIUser(filepath.Join(paths.InstallDir,"TailD","TailD.Background.exe"),nil); err != nil { return installResult{}, err }
	return installResult{Action:"owner-collector-resume-dispatched"},nil
}
