# Experiments

## Format capture

GT-AX11000, eth6, monitored peer `A0:36:BC:9B:BF:89`, channel 4, interval
500 ms: 16 records. A second check at 100 ms: 98 records. In both cases,
the dynamic words occupy bytes `0x60..0x13f`, and the tail alternates between
two values. In the second capture, the driver reported 99 transfers, 1 ACK
failure, and 0 overflows; 98 records were saved.

## Motion test

Session `a184adec-4489-4322-996e-41b059851ed4`, 60 seconds, 592 records.
One person stood in the long room, then waved both arms, then stood still again.
According to the user, no other people were moving. Median change in
normalized amplitude: 0.0189 initially, 0.1316 during motion, 0.0181 afterward.
The interval with high change was approximately 13.0–38.6 s. Chat commands were not
synchronized with the recording clock, so the boundaries are approximate.

## Position test

Session `60d03eaf-0351-4b28-ad17-d169bc5f2ac1`, 60 seconds, 595 records.
Three coarse segments: near the router, the middle of the room, and the far end.
Estimated median RMS amplitudes: 1586, 1545, and 1527 raw units. Distances
between mean normalized profiles: 0.597, 0.759, and 0.315. Transitions
between positions fall within the windows, and annotations were made through chat commands.
The result shows sensitivity to scene position, but does not provide a person's
coordinates and is not a trained room classifier.

## Confounded test

The first session, `c2cd2e65-6601-4b07-be59-2bb2a41773c3`, includes the user's father
moving in the same room throughout the recording. It is retained as a collection check,
but is not used to draw conclusions about the user's hand movements.
