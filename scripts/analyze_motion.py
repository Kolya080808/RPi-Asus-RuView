import sqlite3,json,struct,pathlib
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
ROOT=pathlib.Path(__file__).resolve().parent.parent
IDS=["c2cd2e65-6601-4b07-be59-2bb2a41773c3","b1819fbf-18a3-4053-8cee-9b56f3783d5f"]
db=sqlite3.connect(ROOT/"history-snapshot.sqlite3")
fig,axes=plt.subplots(2,2,figsize=(12,6),layout="constrained")
report={"confound":"User reported another person walking; no segment is verified motion-free. Hand-motion attribution invalid.","timing":"Manual chat cues are delayed; horizontal time uses unverified microsecond-like device timer.","sessions":[]}
for col,sid in enumerate(IDS):
 rows=list(db.execute("select raw from records where session=? order by seq",(sid,)))
 r=[x[0] for x in rows if len(x[0])>=320]
 raw=np.array([struct.unpack_from("<112h",x,96) for x in r],dtype=float)
 z=raw[:,::2]+1j*raw[:,1::2]
 a=np.abs(z)
 timers=np.array([struct.unpack_from("<I",x,20)[0] for x in r],dtype=np.int64)
 delta=np.mod(np.diff(timers),2**32)/1e6
 t=np.r_[0,np.cumsum(delta)]
 norm=a/np.maximum(np.sqrt(np.mean(a*a,axis=1,keepdims=True)),1e-9)
 step=np.sqrt(np.mean(np.diff(norm,axis=0)**2,axis=1))
 power=np.sqrt(np.mean(a*a,axis=1))
 axes[0,col].plot(t,power,lw=.8,color="#2166ac")
 axes[1,col].plot(t[1:],step,lw=.7,color="#bd5727",alpha=.75)
 if len(step)>10:
  axes[1,col].plot(t[10:],np.convolve(step,np.ones(10)/10,mode="valid"),color="#542788",lw=1.5,label="10-sample average")
 axes[0,col].set_title(["Main session (movement confounded)","Follow-up session (baseline unverified)"][col])
 axes[0,col].set_ylabel("Amplitude RMS (raw units)")
 axes[1,col].set_ylabel("Normalized amplitude step (RMS)")
 axes[1,col].set_xlabel("Seconds since first sample (timer hypothesis)")
 axes[1,col].legend(loc="upper right",fontsize=8)
 for ax in axes[:,col]:ax.grid(alpha=.2)
 sections=[("all",0,float(t[-1])+1)]
 if col==0:sections +=[("early_2_12_seconds",2,12),("later_25_38_seconds",25,38)]
 item={"id":sid,"records":len(r),"duration_candidate_s":float(t[-1]),"timer_gap_median_s":float(np.median(delta)),"timer_gap_max_s":float(np.max(delta)),"segments":[]}
 for label,lo,hi in sections:
  mask=(t>=lo)&(t<hi); dm=(t[1:]>=lo)&(t[1:]<hi)
  item["segments"].append({"label":label,"n":int(mask.sum()),"amplitude_rms_median":float(np.median(power[mask])),"normalized_step_median":float(np.median(step[dm])),"normalized_step_p90":float(np.quantile(step[dm],.9))})
 report["sessions"].append(item)
fig.suptitle("CSI exploratory check — another person was moving; no pose or motion attribution",fontsize=12)
fig.savefig(ROOT/"motion-confounded.png",dpi=150)
(ROOT/"motion-confounded.json").write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
