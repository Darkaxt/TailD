// Copyright (c) Tailscale Inc & contributors
// SPDX-License-Identifier: BSD-3-Clause

// TailD-owned distribution overlay. The fixed installed helper verifies the
// dedicated signed complete-product installer, rather than the TailDNS channel.
package taildnsupdate

import (
	"context"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"

	"golang.org/x/sys/windows"
	"tailscale.com/types/logger"
)

func StartLatest(ctx context.Context, logf logger.Logf) error {
	if err := ctx.Err(); err != nil { return err }
	executable, err := os.Executable()
	if err != nil { return err }
	helper := filepath.Join(filepath.Dir(executable), "TailD", "TailD.Setup.exe")
	command := exec.Command(helper, "update")
	// No CommandContext: a caller cancellation must never kill a downloaded
	// installer, abandon a transaction or release its lifecycle supervision.
	command.SysProcAttr = &windows.SysProcAttr{CreationFlags: windows.CREATE_NO_WINDOW}
	if err := command.Run(); err != nil { return fmt.Errorf("TailD signed updater: %w", err) }
	logf("TailD update: signed installer dispatch completed")
	return nil
}
