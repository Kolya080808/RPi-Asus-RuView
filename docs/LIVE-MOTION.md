# Live motion graph, directly from ASUS

From PowerShell in the repository root:

```powershell
python .\scripts\live_motion.py
```

A separate window opens immediately. Press **Start** to receive real CSI from
the ASUS. The top panel shows amplitude RMS; the bottom shows changes between
normalized frames with a prominent smoothed line. **Stop** ends capture; closing
the window also requests Stop and waits for cleanup. No Raspberry Pi is used.

The default session limit is 60 seconds. For up to ten minutes:

```powershell
python .\scripts\live_motion.py --seconds 600
```

Alternatively run `scripts/live-motion.ps1`. Dependencies on the computer are
Python with Tk, Matplotlib, and Paramiko. The existing `router_key` and
`router_known_hosts` in the repository root are used with strict host-key
verification; no credentials are included in Git. The default router is
`192.168.50.1`, user `admin`, interface `eth6`, monitored peer
`A0:36:BC:9B:BF:89`, interval 100 ms.

## Reading the graph

- Move and pause to compare the response. The graph measures radio-scene change,
  not a body part, location, or calibrated probability of motion.
- The smoothing slider sets the causal exponential filter time constant from
  0.1 to 3 seconds. Smaller values respond faster; larger values show a steadier
  line with more delay. It affects new samples, not already displayed history.
- The display refreshes approximately ten times per second and shows the latest
  60 seconds. Transport buffering can add latency; refresh rate is not a guarantee
  of measurement latency. Device timestamps remain provisional.
- The lower y-axis begins at 0.00 and starts at 0.10 when the data fit. It expands
  in 0.10 increments when higher peaks occur, so measured changes are never cut off.
- After two seconds without valid records, the window explicitly shows
  **NO NEW DATA**. A frozen line does not mean that the room is still.
- Timing gaps reset smoothing and interrupt the line. Unsupported profiles or
  timer resets stop the run with an error.

## Data and cleanup

Each Start creates `recordings/live-TIMESTAMP/`, with raw router text, a JSONL
stream of the useful first 320 bytes per record, receive timestamps, router
before/after observations, capture status, and cleanup verification. The full
printed tail is retained only in the router text log. After completion or Stop,
the UI also saves computed samples and `motion.png` for the displayed view.
All samples remain in the data files even when the window has scrolled past them.

No remote scripts, firmware settings, packages, or services are installed.
The temporary shell checks that CSI is disabled, the peer list is empty, and
no csimond process is running before starting. It enables only the known peer,
owns its collector PID, and disables monitoring/removes the peer on exit.
The sleep is bounded and interruptible. Stop closes the PTY, and the shell
HUP/EXIT trap performs cleanup. The worker checks the final router state before
reporting cleanup as verified. If verification fails, inspect the logs and use
the existing rollback inspection after the bounded capture has ended.

Do not run another capture tool simultaneously. Router-side preflight guards
reject an already active monitor but are not an atomic lock shared with legacy
tools. Power loss, hard process termination, or a broken network can prevent
immediate verification; the recording limit is a fallback, not proof of cleanup.

## Verification

On 2026-09-30, a direct ASUS capture delivered its first parsed record after
approximately 1.57 seconds, while the capture was still running. Stop was
requested after 20 records; the run finished in approximately 3.82 seconds.
Final checks confirmed CSI disabled, an empty peer list, and no csimond process.
This verified transport and cleanup, not motion-classification accuracy.
Offline tests cover arbitrary stream fragmentation, early record emission,
smoothing, missing intervals, unsupported profiles, and timer rollover.

In the user screenshot from the same date, 237 live frames match the first 320
bytes of all 237 complete records in the saved router text exactly. Median device
interval was 100.018 ms. The largest consecutive normalized-amplitude change
was about 0.336, so a fixed 0.10 axis would still hide real peaks. The display
therefore starts at 0.10 and grows in 0.10 increments to fit the full signal.
