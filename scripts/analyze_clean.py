import sqlite3,struct,json,pathlib
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
root=pathlib.Path(__file__).resolve().parent.parent
evidence=root/'evidence'
reports=root/'docs'
sid="a184adec-4489-4322-996e-41b059851ed4"
c=sqlite3.connect(root/"history-snapshot.sqlite3")
r=[x[0] for x in c.execute("select raw from records where session=? order by seq",(sid,))]
assert all(len(x)==2048 for x in r)
h=np.array([struct.unpack_from("<112h",x,96) for x in r],float)
z=h[:,::2]+1j*h[:,1::2]
a=np.abs(z)
timer=np.array([struct.unpack_from("<I",x,20)[0] for x in r],dtype=np.int64)
t=np.r_[0,np.cumsum(np.mod(np.diff(timer),2**32))/1e6]
# Normalize each packet to reduce packet-dependent gain.
unit=a/np.maximum(np.sqrt(np.mean(a*a,axis=1,keepdims=True)),1e-9)
step=np.sqrt(np.mean(np.diff(unit,axis=0)**2,axis=1))
power=np.sqrt(np.mean(a*a,axis=1))
windows=[("still_before",1,8),("arms_moving",16,30),("still_after",43,54)]
rows=[]
for name,lo,hi in windows:
 mask=(t>=lo)&(t<hi); dmask=(t[1:]>=lo)&(t[1:]<hi)
 rows.append({"name":name,"seconds":[lo,hi],"samples":int(mask.sum()),"amplitude_rms_median":float(np.median(power[mask])),"step_median":float(np.median(step[dmask])),"step_p90":float(np.quantile(step[dmask],.9)),"step_over_0_1_fraction":float(np.mean(step[dmask]>.1))})
report={"session":sid,"records":len(r),"timer_duration_s":float(t[-1]),"step_definition":"RMS consecutive difference in 56 tone amplitudes, each packet normalized by its RMS amplitude", "windows":"Conservative rough windows from chat cues; action timestamps are not synchronized to device", "other_person_moving":False,"user_report":"Only user moved in long room", "segments":rows,"header_0x10_unique":sorted(set(hex(struct.unpack_from("<I",x,16)[0]) for x in r)),"header_0x40_unique":sorted(set(hex(struct.unpack_from("<I",x,64)[0]) for x in r)),"rssi_like_median":np.median(np.array([struct.unpack_from('4b',x,28) for x in r]),axis=0).tolist(),"user_annotation":{"other_person_moving":False,"source":"user report after test","activity_sequence":["stand still","wave both arms in place","stand still"],"ground_truth_precision":"manual chat cues; delayed and not synchronized","inferred_motion_interval_timer_s":[13.002699,38.607353],"measurement":"normalized consecutive CSI amplitude RMS step","segment_medians":[float(row["step_median"]) for row in rows],"interpretation":"motion detection in this one experiment; limb-specific pose not established"}}
print(json.dumps(report,indent=2));(reports/'clean-motion-analysis.json').write_text(json.dumps(report,indent=2))
fig,(ax0,ax1)=plt.subplots(2,1,figsize=(12,6),sharex=True,layout="constrained")
ax0.plot(t,power,lw=.7,label="CSI amplitude RMS")
ax1.plot(t[1:],step,lw=.7,label="Change between adjacent normalized CSI frames")
ax1.plot(t[10:],np.convolve(step,np.ones(10)/10,mode='valid'),lw=1.5,label="10-sample mean")
colors={'still_before':'#b7d8ca','arms_moving':'#f4bf9f','still_after':'#b7d8ca'}
for row in rows:
 for ax in [ax0,ax1]:ax.axvspan(*row['seconds'],color=colors[row['name']],alpha=.35)
ax0.set_ylabel("Amplitude RMS, raw units");ax1.set_ylabel("Normalized CSI step");ax1.set_xlabel("Seconds since first CSI record; timer is provisional")
for ax in [ax0,ax1]:ax.grid(alpha=.2);ax.legend(loc="upper right")
fig.suptitle("One-person arm movement test; window timing approximate")
fig.savefig(evidence/'clean-motion-analysis.png',dpi=150)
