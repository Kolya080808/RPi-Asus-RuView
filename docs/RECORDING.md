# Collection and history on Raspberry Pi

Access: ssh pi@192.168.50.100. On the Pi:

```sh
python3 /home/pi/ruview-lab/recorder.py capture --seconds 20 --interval-ms 100
python3 /home/pi/ruview-lab/recorder.py history
python3 /home/pi/ruview-lab/recorder.py export SESSION_ID
python3 /home/pi/ruview-lab/motion.py SESSION_ID
```

The collector connects directly from the Pi to the ASUS using a dedicated key.
A PC is not needed to acquire or save data. Python uses only the standard library.
Operation is limited to a single session of 5–60 seconds. After the session, the monitor
is disabled and the temporary peer entry is removed. There is no service or autostart.

History: /home/pi/ruview-lab/history.sqlite3. It contains raw records, provisional
decoding results, session start/end times, parameters,
complete diagnostic output, and errors. The time of each record from field 0x14
has not yet been tied to UTC; future training with a camera requires synchronization.
After capture, `recorder.py` automatically runs `motion.py`: the first 8 seconds
serve as a baseline, after which a sustained increase in normalized amplitude change
is recorded as an event in the `motion_samples` and `motion_events` tables. This
indicates motion across the entire scene. It does not produce a skeleton, body parts, or heart rate.
There are no video recordings or computed skeletons yet. History is currently accessed through history
and export; a web player has not yet been implemented.

Retention duration is undecided: there is no automatic deletion. Once the
database reaches 256 MiB, new captures are blocked until manual archival.
Text diagnostic logs increase storage size; long-term storage requirements
cannot be estimated from the 320-byte useful block alone.

Verified 2026-09-29: session 40ddd901-0f56-44d4-bebd-0c74c4d6eb04,
10 seconds, 100 ms, 98 records. All are 2048 bytes. The 96:320 region updates
in every packet; the tail repeats A/B. The driver counted 99 transfers,
1 ACK failure, and 0 overflows; the collector does not yet guarantee lossless acquisition.
An unsuccessful attempt was saved with failed status, not presented as a successful recording.

The decoder profile is limited to the current eth6/channel 4 setup. A different header is not
silently decoded: the original bytes are saved along with a profile error.
The dynamic region boundary has been confirmed twice; the physical meaning of I/Q,
subcarrier order, and compatibility with the pose model remain hypotheses.

Pi → ASUS access is currently added to the runtime file /root/.ssh/authorized_keys;
after an ASUS reboot, the firmware may recreate it from its settings.
Persistent SSH settings in NVRAM were not changed.
