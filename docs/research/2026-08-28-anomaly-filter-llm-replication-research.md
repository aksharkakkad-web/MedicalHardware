# Implementation and Replication Research for a Personalized Contactless-Monitoring Anomaly Filter and LLM Interpretation System

## Executive recommendation and architecture corrections

The previous architecture is directionally correct, and the strongest evidence I found does **not** justify replacing it with an end-to-end multimodal neural model.

The V1 I would build is:

> **deterministic sensor validation → explicit quality/availability → normalized sensor-specific features → frozen personal robust baselines → persistent robust deviations → event-specific late fusion/state machines → rich anomaly episode → one retrieval-capable structured LLM interpretation call → deterministic policy validation → existing event workflow.**

The core production anomaly detector should be **Candidate A: transparent median/MAD + empirical-quantile personalization**, augmented by **simple deterministic state machines for safety events** and a small amount of **EWMA-style sustained-change evidence**. **Isolation Forest belongs in shadow mode**, not in the authority path. PELT belongs in replay/offline analysis, not the real-time alert path.

This recommendation follows the strongest transfer-relevant evidence found:

| Evidence | Limitation | Transferability | Recommendation |
|---|---|---|---|
| In PRISM's 44-home dementia-monitoring dataset, models trained/updated on a patient's own data performed better than cross-patient or pooled models, directly demonstrating strong individual behavioral variation. citeturn20view2turn21view2 | PRISM injected synthetic spike/variance/on-off anomalies and optimized classification accuracy rather than continuous caregiver alert burden. citeturn21view0turn21view2 | **High** for personalization; **low** for its DNN detector. | Keep resident-specific baselines; do not copy PRISM's neural thresholding. |
| A real-world UK dementia-monitoring study analyzed 9,363 patient-days from 15 households and found a personalized Contextual Matrix Profile approach worked best with approximately 7–14-day recent-history windows; its reported best setup had 84.3% recall and approximately 32 alerts over an average 624-day timeline. citeturn20view3 | It operated primarily at daily granularity using PIR room activity, not second-scale radar/thermal behavior, and the paper explicitly identifies visitors, other household members and attribution as unresolved sources of anomaly noise. citeturn20view3 | **High** for recent-history baselines, personalization, operational alert metrics and explicit handling of other people; **low** for instantaneous anomaly mechanics. | Use a rolling recent-history personal baseline and measure alerts per resident-day, but use faster windows for physical behavior. |
| mmFall used 4-D radar point clouds, normal-only anomaly reconstruction and a height-drop constraint; a 1-second window at 10 radar frames/s detected 49/50 staged falls with two false alarms in the published evaluation. citeturn13view0turn13view1turn13view2turn14view0 | Only two similar-sized participants, staged activities, one relatively empty room, and no continuous false-alert/day evaluation. The authors themselves note generalization and engineering limitations. citeturn13view2turn14view0 | **High** for fast fall mechanics; **poor** justification for a production neural anomaly detector. | Copy the *structure*: rapid vertical change + height collapse + post-transition evidence. Do not copy the deep model or fixed 0.6 m threshold as a production truth. |
| TI's current Radar Toolbox exposes fall detection, people tracking and vital-sign examples for IWR6843-class hardware. TI's fall implementation exposes an auditable height-history/state-style implementation, while TI support material also documents practical implementation bugs and configuration dependence. citeturn15search0turn15search3turn15search13 | TI's vital-sign implementation is not fully open at the same level: TI support has stated that some IWR6843 vital-sign source requires NDA access, whereas people-tracking code is public. citeturn15search25 | **High** as radar feature/quality reference; **medium** as an algorithm you can reproduce exactly. | Consume tracks, point clouds, height/activity and quality outputs; isolate Mahin's radar algorithm behind the normalized interface. Treat respiration as quality-gated and cardiac output as experimental. |
| Low-resolution thermal work using MLX90640 at 32×24 demonstrated that explicit background modeling substantially improves person detection and showed successful MCU-scale operation around 8 FPS; the dataset contains 96k frames collected at 12 locations. citeturn3view0 | Published performance is person detection, not continuous fall/event monitoring. Its initial-background assumption requires an empty scene and therefore cannot be blindly transferred to an occupied care room. citeturn3view0 | **High** for thermal preprocessing and quality; **medium** for posture features. | Maintain a protected thermal background/environment model, but freeze updates around occupants, ambiguity and setup changes. |
| Espressif's maintained `esp-csi` reference implementation supports ESP32-S3 and exposes RSSI, RF noise floor, timestamps/reception metadata and CSI; it now includes human-presence/motion examples with on-site training. fileciteturn2file0L1-L10 | Espressif explicitly describes CSI as extremely sensitive to environment, and its recommended acquisition methods depend on AP/device/channel geometry. fileciteturn2file0L1-L10 | **High** for CSI acquisition/quality design; **low** for treating CSI as location ground truth. | CSI stays a supporting sensor. Wi-Fi channel/AP/layout changes must invalidate or freeze CSI baselines. |

### The part the previous architecture got most right

The strongest result from this investigation is that **you should not ask one anomaly model to simultaneously solve signal quality, resident identity, behavior semantics, sensor fusion, diagnosis and safety response**.

That architecture would be elegant on a diagram and terrible to debug.

PRISM shows why resident-specific behavior matters; the Minder/CMP study shows why recent-history personalization and operational alert rates matter; radar fall work shows that fast physical events need a different timescale from routine change; low-resolution thermal research shows preprocessing/background quality can determine whether later recognition works at all; and Wi-Fi sensing work demonstrates domain sensitivity to environment. citeturn21view2turn20view3turn13view2turn3view0 fileciteturn2file0L1-L10

So the right V1 is deliberately **heterogeneous**:

**Fast safety path**

`source-rate radar/thermal evidence → deterministic fall-like state machine → provisional event if physical evidence is sufficiently strong`

**General behavioral path**

`1-s normalized frames → quality gates → resident baseline → robust deviations → persistence/hysteresis → anomaly episode → LLM interpretation`

**Slow behavioral path**

`minute/hour/day summaries → recent routine baseline → gradual-change indicators → interpretation/awareness rather than immediate emergency action`

That separation is more important than the exact anomaly algorithm.

### What I would change from the previous conclusions

I would make six material changes.

**First, do not define “quality-weighted fusion” as a weighted average in V1.** A weight such as `radar=0.6, thermal=0.3, CSI=0.1` creates false precision and can obscure contradictions. Instead use `GOOD / LIMITED / UNUSABLE`, preserve sensor-specific evidence, and implement event-specific logical fusion. A missing sensor should reduce evidence completeness/confidence without mathematically making an observed deviation smaller.

**Second, make median/MAD the main score but store quantiles as first-class baseline fields.** MAD can collapse to zero for quantized or near-constant features. The baseline should therefore contain median, MAD, IQR and tail quantiles, with a documented scale floor.

**Third, do not make EWMA/CUSUM a competing V1 architecture.** EWMA is useful as a *progression feature* for sustained movement or respiration shifts. CUSUM is sensitive to its assumed reference distribution/shift and adds threshold-tuning surface area. Neither solves data quality, baseline poisoning or episode lifecycle. EWMA originated as a way of emphasizing persistent shifts, while PELT solves a different problem—optimal segmentation/change-point location rather than real-time safety classification. citeturn25search22turn25search9

**Fourth, use approximately a two-week baseline horizon as the V1 starting horizon for routine features, but do not pretend this transfers exactly to second-level motion.** The strongest directly relevant real-world monitoring evidence found a 7–14-day thresholding window and discusses a two-week recent baseline as balancing sudden and gradual behavioral changes. citeturn20view3

**Fifth, define baseline contamination as a testable correctness failure, not a statistical nuisance.** Any observation that is away, multiple-person, degraded, anomalous, unresolved, recalibrating or from a materially changed setup is *ineligible by construction*. It should never enter an adaptive algorithm and later be “down-weighted.”

**Sixth, make monitoring degradation a parallel anomaly family with priority over behavioral interpretation.** A frozen CSI stream, shifted thermal background, track collapse after radar movement, or timestamp disorder is not “unusually still resident behavior.” It is an instrumentation problem.

The blunt conclusion is this: **your largest V1 technical risk is probably not picking the wrong anomaly algorithm. It is accidentally allowing bad attribution, bad quality or bad baseline updates to make normality itself wrong.**

## Evidence base and replication audit

I reviewed the closest implementation-relevant sources I could locate across radar, low-resolution thermal sensing, Wi-Fi CSI, real-world aging-in-place anomaly detection, simulator-driven systems, manufacturer reference systems and classical anomaly/change-detection methods. “NR” below means the relevant implementation detail was not reported in the accessible primary material; I have deliberately not filled gaps by inference.

**Reproducibility labels**

`R` = paper/docs are detailed enough to reimplement the relevant part.  
`C` = accessible implementation/code.  
`D` = accessible dataset or data-access mechanism.  
`I` = independent reproduction located for the claimed operational result.

None of the systems reviewed qualifies as `I` for **continuous one-resident contactless monitoring with operational false-caregiver-events/day**, which is the metric that ultimately matters here.

### Implementation detail audit

| Source/system | Inputs and modality | Rate / window | Preprocessing and features | Baseline / personalization | Detector and thresholding | Persistence / lifecycle / missing data | Reproducibility |
|---|---|---|---|---|---|---|---|
| **mmFall, Jin et al.** | mmWave 4-D point cloud `(x,y,z,Doppler)` plus body centroid. citeturn13view0turn14view0 | AWR1843; 10 FPS; model input 10 frames = 1 s; each frame resampled to 64 points. citeturn14view0 | FFT/CFAR/MTI radar processing; coordinate transformation; tracking can use clustering/Kalman mechanisms; HVRAE receives 10×64×4 tensors. citeturn13view0turn13view1 | Normal ADL-only training; not longitudinal resident personalization. | HVRAE reconstruction/variational anomaly loss **AND** centroid height drop; published height-drop threshold 0.6 m. citeturn13view1turn13view2 | One-second detection window. Missing modality irrelevant because radar-only. Episode merging/hysteresis NR. | **R**; code is mentioned by the work, but a maintained source repository was not verified in this investigation. |
| **TI Radar Toolbox fall reference** | IWR6843-class tracked target height/position/motion. citeturn15search0turn15search20 | Current implementation exposes a fall-history buffer; TI support showed a default `secondsInFallBuffer=2.5` and frame-time dependency. citeturn15search13 | Device people tracking and target height; Python-side fall detection in the visualizer in the referenced implementation. citeturn15search13turn15search20 | No resident-personal longitudinal baseline. | Height/history style rule; exposed `fallingThresholdProportion=0.6` in the support-referenced implementation. citeturn15search13 | Explicit temporal history buffer. Sensor missing/failure policy belongs to surrounding application, not fall algorithm. | **R+C** within TI's toolbox/package terms. |
| **TI Vital Signs with People Tracking** | IWR6843 people tracking plus micro-motion/vital-sign extraction. citeturn15search3turn15search9 | TI markets vital-sign monitoring up to specified ranges and breathing-rate capability; exact usable rates depend on lab configuration. citeturn15search9 | Detection/tracking onboard sensor, then target-specific vital-sign analysis. citeturn15search3 | NR. | Signal-processing reference rather than anomaly detector. | TI forum reports practical stabilization/configuration behavior; full vital-sign source for some IWR6843 configurations has required NDA access. citeturn15search6turn15search25 | **Partial R+C** for tracking; **not fully open** for all vital-sign internals. |
| **Vandersteegen et al. MLX90640 person detector** | 32×24 MLX90640 temperature images. citeturn3view0 | Dataset at 8 FPS; 96k frames; 190 clips; 12 locations. citeturn3view0 | Background subtraction; detected regions excluded from background updates; EMA background `α=0.99`, update every 25 frames; compact YOLO-style detector. citeturn3view0 | Environmental background, not resident behavioral baseline. | Supervised person detection; confidence/F1 threshold selected from validation. | Explicit background maintenance; initial model assumes three person-free frames, a dangerous assumption for our product. citeturn3view0 | **R+D**; particularly reproducible preprocessing. |
| **InfoLab-SKKU Thermal Human Detection** | MLX90640 raw 32×24 thermal. citeturn27search3 | Dataset/code aimed at real-time human detection/behavior recognition. | Repo includes dataset/model implementation artifacts. citeturn27search3 | No personal longitudinal baseline. | Learned human/behavior recognition. | Operational anomaly lifecycle NR. | **C+D**; repository is public under MIT and was last pushed in October 2024. fileciteturn4file0L1-L10 |
| **eHomeSeniors** | MLX90640 32×24 plus another privacy-preserving thermopile configuration. citeturn22search0turn19search4 | Staged fall sequences; exact acquisition configuration is documented in the paper rather than a continuous deployment specification. | Paper includes a preliminary heuristic based on body-temperature pixels/trajectory features. | None. | Fall/ADL dataset, not production anomaly lifecycle. | NR. | **D + partially R**. The published dataset contains approximately 448 staged falls from six volunteers according to the original-paper copy. citeturn24search3turn24search4 |
| **Taramasco et al. multimodal fall dataset** | 60–64 GHz radar, FIR thermal, 8×8 LiDAR and smartphone accelerometry. citeturn17search0turn17search2 | Ten simulated fall types by ten participants. citeturn17search1 | Dataset characterization uses instantaneous signal norms and temporal differences across modalities. citeturn17search1 | None. | Dataset rather than deployed detector. | Provides synchronized modalities useful for fusion experiments. | **D**; extremely relevant as a multimodal fall-validation source, but not evidence of production alert performance. |
| **MM-Fi** | RGB, depth, LiDAR, mmWave point clouds and Wi-Fi CSI. citeturn26search0turn26search16 | >320k synchronized frames; 40 subjects; 27 categories in the published NeurIPS/arXiv version. citeturn26search0 | Dataset loaders and modality-specific benchmark pipelines. | Cross-domain benchmark splits, not resident adaptation. | Action/pose models rather than anomaly detection. | Multiple modalities are synchronized, making it valuable for interface/fusion testing. | **C+D**. Author repository is public; GitHub currently exposes no repository-level license declaration, so accessibility must not be confused with redistribution rights. fileciteturn3file0L1-L10 |
| **Widar3.0** | Commodity Wi-Fi CSI transformed into body-coordinate velocity profiles. citeturn26search1turn26search5 | Gesture segments rather than continuous monitoring. | Designed explicitly for cross-domain robustness across environment/location/orientation. citeturn26search1turn26search5 | Cross-domain learned representation rather than individual baseline. | Gesture classifier. | No monitoring degradation/event lifecycle. | **R+C+D** through the authors' project resources; valuable principally as evidence that CSI domains shift substantially. citeturn26search5 |
| **Espressif ESP-CSI / ESP Wi-Fi sensing** | ESP32-series CSI including ESP32-S3; amplitude/phase/channel state plus RSSI, RF noise floor, reception metadata. fileciteturn2file0L1-L10 | Packet-driven; configurable. | Acquisition examples, CSI parsing, human activity/presence examples, local calibration. fileciteturn2file0L1-L10 | Some demonstrations use on-site training; no resident-longitudinal caregiving baseline. | Application-specific sensing component. | Acquisition quality is strongly dependent on channel/device/environment configuration. fileciteturn2file0L1-L10 | **C**, Apache-2.0 repository; actively updated in 2026. fileciteturn1file0L1-L10 |
| **Mertens et al. MoBaDDD** | Binary room motion/presence patterns. citeturn27search2turn27search6 | Day divided into time intervals; experiments discuss resolutions down to ~60 s; each current day is compared to preceding days. citeturn27search6turn27search19 | Reference day formed by majority vote for each time interval from preceding days. Hamming distance measures deviation. citeturn27search19 | Explicit single-resident recent-history baseline. | Outlier-day thresholding. | Synthetic evaluation inserted 20 subtle deviating days; designed to avoid trivially obvious perturbations. citeturn27search6 | **R**. Particularly valuable because the method is simple, resident-specific and simulator-testable. |
| **Bijlani et al. Contextual Matrix Profile** | Daily aggregated PIR movement counts/durations/change patterns by home location. citeturn20view3 | Daily features; best reported thresholding window 7–14 days; 7-day multivariate model highlighted in results. citeturn20view3 | Matrix Profile / contextual nearest-subsequence distances, univariate and multidimensional anomaly scores. | Patient-specific patterns and sliding recent-history thresholding. citeturn20view3 | Distance-based anomaly score; top contributing features exposed. | Authors explicitly identify visitors, pets, other household members and subsequent-window evidence as important unresolved issues. citeturn20view3 | **R**, but clinical source data are not an unrestricted public benchmark. |
| **PRISM** | 22 types of in-home IoT measurements from 44 PLWD households, April 2019–June 2021. citeturn21view0 | Experiments with time windows from 15 min through hours/day scale. citeturn21view0 | Raw readings plus elapsed time between readings. | Explicit same-patient versus other-patient comparisons. citeturn21view2 | Two-layer neural anomaly model; anomaly if validation loss exceeds `α × mean(training loss)`; synthetic on/off, variance and spike anomalies. citeturn21view0 | Model degradation over time identified as an open issue. citeturn21view3 | **R**, but not a reproducible public caregiver-alert benchmark. |
| **Tanaka et al. long-term simulator system** | Simulated smart-home sensor observations parameterized by room, sensor layout and resident behavior. citeturn27search0turn27search4 | Different detectors operate at durations appropriate to the anomaly: second-scale falls through multi-day/week-scale behavior. citeturn27search0 | Standardized sensor-data processing plus simple per-anomaly classifiers. | Simulator parameters can be individualized. | Separate detectors for six abnormal-behavior types. | Explicitly recognizes that different anomalies require different temporal resolutions. | **R conceptually**. Evaluated against simulated sequences representing nine years; some long-duration categories reportedly achieved sensitivity >0.9 with <1 false alarm/50 days, but validity depends directly on simulator realism. citeturn27search0 |
| **Isolation Forest** | Generic multivariate feature vectors. | No required fixed window; batch/subsample algorithm. | Random recursive partitions isolate unusual samples. | Personal model possible if trained on resident baseline. | Short isolation paths imply anomaly. Original method was designed for efficient low-memory anomaly scoring. citeturn25search0 | Native algorithm does not solve temporal persistence, missing modalities, baseline poisoning or episode handling. | **R+C** via multiple mature implementations; original 2008 method is directly reproducible. citeturn25search0turn25search20 |
| **PELT** | Univariate or multivariate time series with a chosen segment cost. | Batch/offline sequence. | Dynamic-programming segmentation with pruning. | Baseline implicit in cost model, not personalized by itself. | Minimizes penalized segmentation objective exactly; under stated conditions computational cost is linear in sequence length. citeturn25search9turn25search5 | Detects regime boundaries; does not itself define caregiver event lifecycle. | **R+C** through standard change-point packages. |

### What the evaluation evidence actually proves

There is a recurring research trap here: **high staged-window accuracy is not equivalent to low operational false-alert burden**.

mmFall's 98% result is interesting, but it is 49/50 staged falls in a two-person controlled dataset with two false alarms—not evidence of 24/7 performance. citeturn13view2turn14view0

MM-Fi's scale is impressive—over 320,000 synchronized frames and 40 participants—but it is fundamentally a pose/action benchmark, not a personalized anomaly-monitoring trial. citeturn26search0

Widar3.0 is important evidence that sophisticated Wi-Fi sensing can generalize better across some predefined domains, but gesture classification segments do not tell you how many false caregiver events an always-on room deployment will generate. citeturn26search1turn26search5

The most product-relevant operational reporting came instead from the Minder/CMP work because it reports alerts over hundreds of days and explicitly discusses real-world visitors, household members, missingness and noisy labels. Its reported 32 alerts over an average 624-day timeline is far more useful to your product architecture than “99% accuracy” on balanced staged windows. citeturn20view3

### Methods worth reproducing

**Robust resident baselines.** Median/MAD remains defensible. MAD is a robust scale estimator based on the median of absolute residuals from the median, which is precisely the property wanted when the baseline may contain a limited amount of unrecognized unusual behavior. citeturn25search7

**Recent-history routine baselines.** Both the simple MoBaDDD approach and the real-world Contextual Matrix Profile work show the value of comparing a resident against recent behavior instead of a population template. citeturn27search19turn20view3

**Fast physical-state transitions.** mmFall and TI's fall reference both preserve explicit temporal/height mechanics rather than classifying a single static frame. citeturn13view2turn15search13

**Protected environmental/background adaptation.** Thermal person-detection work specifically excludes detected foreground regions from its background updater. That is directly analogous to your rule that anomaly periods must not enter normality. citeturn3view0

**Event-specific modality logic.** Taramasco's synchronized multimodal data exists precisely because physically different sensors can contribute complementary evidence. It supports testing late fusion; it does not justify averaging modalities into a single opaque embedding. citeturn17search0turn17search2

**Isolation Forest as a challenger.** Isolation Forest is cheap, deterministic when seeded, easy to replay and can expose anomalies not encoded in hand-written feature thresholds. Its weakness is equally important: it has no concept of persistence, safety semantics, modality failure or calibration eligibility. citeturn25search0turn25search20

**PELT for offline regime discovery.** PELT is ideal for asking, after replay, “was there a durable change point around this date?” It is not the algorithm I would place between a radar frame and an urgent fall-like event. citeturn25search9

### Methods I would not copy into V1

Do **not** copy mmFall's HVRAE as the general anomaly filter. The staged evaluation is too small and homogeneous to justify the complexity. citeturn14view0turn13view2

Do **not** copy a fixed population fall threshold such as `0.6 m` as if it were clinically meaningful. mmFall's threshold belonged to its mounting geometry and two similar-sized participants; TI's implementation likewise exposes configuration-specific threshold/history parameters. citeturn13view2turn15search13

Do **not** copy EAVISE's “three empty startup frames” thermal-background initialization into an occupied resident room. Its background exclusion logic is valuable; its empty-start assumption is not universally transferable. citeturn3view0

Do **not** copy PRISM's DNN loss threshold. It was tested against artificially injected anomalies and used accuracy as the principal metric. The personalization result transfers; its detector design does not. citeturn21view0turn21view2

Do **not** make Wi-Fi CSI a required modality for caregiver safety. Espressif's own material makes clear how sensitive CSI is to environment and acquisition topology, while Widar exists largely because environmental/domain shift is a fundamental CSI problem. citeturn26search1turn26search5 fileciteturn2file0L1-L10

Do **not** use a pooled population anomaly model as the resident's definition of “normal.” PRISM provides direct evidence against that simplification. citeturn21view2

## Candidate designs and the recommended production filter

### Candidate comparison

| Design | Core algorithm | Strengths | Failure modes | V1 role |
|---|---|---|---|---|
| **Candidate A — transparent personal baseline** | Quality gates → resident median/MAD/quantiles → robust deviation → persistence/hysteresis → episodes | Auditable; straightforward replay; missing features remain missing; easy evidence attribution; no training infrastructure; resident-specific | Misses multivariate combinations where no individual feature is extreme; baseline logic must be carefully protected | **Production authority** |
| **Candidate B — sustained-change detector** | Candidate A normalization → EWMA and optionally CUSUM → sustained-shift evidence | Better sensitivity to small long-duration changes; useful progression field | Highly dependent on tuning/autocorrelation; can confuse slow sensor/environment drift with resident change; CUSUM parameters imply a particular expected shift | **EWMA production evidence only; CUSUM shadow** |
| **Candidate C — multivariable shadow detector** | Personal normalized vectors → Isolation Forest | Finds combinations not explicitly anticipated; computationally cheap; mature implementation | Missing features awkward; anomaly score opaque relative to simple z-scores; instantaneous scores can be noisy; no lifecycle semantics | **Shadow only** |

The answer is therefore **not “pick A, B or C.”**

Build:

> **A as production + a small EWMA progression layer from B + C in shadow mode.**

Keep PELT as a replay-analysis utility.

### Normalized feature contract

The filter should never depend on MLX90640 pixels, radar UART TLVs or ESP32 CSI arrays directly. Mahin's stack should transform those into a stable feature contract.

Use two temporal lanes.

**Fast safety lane — source-rate evidence.** Radar should ideally preserve approximately 10 Hz or better track/kinematic evidence when the final configuration supports it. A 10 FPS, one-second radar sequence is directly precedented by mmFall, while TI's implementation also maintains sub-second/frame-level target histories. This is **evidence-backed as an engineering precedent, not a validated product requirement**. citeturn14view0turn15search13

**Behavior lane — one-second normalized frames.** `1 s` is an **engineering starting hypothesis**. It is deliberately slower than acquisition and faster than the daily/minute anomaly systems reviewed. It minimizes backend volume while preserving movement, inactivity and progression. Validate it by replaying 250 ms, 500 ms, 1 s and 2 s aggregations against real recordings and comparing event delay and false anomaly packets.

Recommended initial feature contract:

| Feature | Meaning | Primary source | Supporting source | Quality requirement | Baseline type |
|---|---|---|---|---|---|
| `presence` | Person evidence in room | radar + thermal late fusion | CSI | At least one GOOD physical modality; conflicting states retained | State probability/rate, not z-score |
| `person_count_hint` | 0 / 1 / possible multiple | thermal + radar tracking | CSI never authoritative | GOOD detection/tracking | No resident baseline |
| `position_xyz_m` | Approximate resident track | radar | thermal XY | GOOD stable track | Median/quantiles by time context |
| `zone_id` | Room region occupied | deterministic position→zone mapping | thermal | GOOD localization | Empirical residence probability |
| `height_m` | Tracked vertical body extent/height | radar | thermal posture | GOOD radar track | Median/MAD/quantiles conditioned on posture where available |
| `vertical_velocity_mps` | Rate of vertical movement | radar | thermal centroid shift | GOOD radar | Median/MAD + extreme tails |
| `horizontal_speed_mps` | Translational movement | radar | thermal motion | GOOD radar | Median/MAD/quantiles |
| `radar_motion_energy` | Source-defined bulk activity measure | radar | — | GOOD | Median/MAD/quantiles |
| `thermal_motion_energy` | Frame-to-frame foreground motion | thermal | — | GOOD thermal background/foreground separation | Median/MAD/quantiles |
| `thermal_floor_proximity` | Geometry consistent with low/floor-level body | thermal | radar height | GOOD person segmentation | Empirical/posture conditional |
| `thermal_uprightness` | Coarse vertical body geometry | thermal | radar height | GOOD segmentation | Empirical/posture conditional |
| `thermal_foreground_area` | Coarse occupied-body thermal area | thermal | — | GOOD thermal scene | Median/MAD |
| `csi_motion_index` | CSI-derived change/motion measure | Wi-Fi CSI | radar/thermal | GOOD channel/config state | Median/MAD/quantiles |
| `csi_periodicity` | Strength of repetitive temporal component | Wi-Fi CSI | radar movement | GOOD CSI | Median/MAD |
| `csi_environment_shift` | Evidence wireless channel itself changed | CSI | room/device metadata | GOOD enough for diagnostics | **Quality/system feature, not resident anomaly** |
| `time_since_meaningful_motion_s` | Time since last reliable movement evidence | deterministic late fusion | all | Presence established and at least one GOOD movement sensor | Empirical quantiles, especially time-of-day |
| `movement_burst_count` | Number of movement bouts per window | radar + thermal independently | CSI | ≥80% usable coverage in window | Median/MAD/quantiles |
| `repetition_score` | Repetitiveness/periodicity of movement | radar movement sequence | CSI | Sufficient valid coverage | Median/MAD/quantiles |
| `respiration_rate_bpm` | Contactless respiration estimate | radar | CSI research-only corroboration | Radar algorithm explicitly says estimate usable | Median/MAD/quantiles |
| `respiration_quality` | Signal quality/coherence/SNR/track stability | radar | CSI diagnostic | Always retained | Quality field; never imputed |
| `heart_rate_bpm` | Experimental radar cardiac estimate | radar | **none for V1 decisions** | Strict experimental quality | Stored only; no caregiver authority |

The 32×24 thermal resolution is native to MLX90640 and is well represented in both eHomeSeniors and public implementation work. citeturn22search0turn27search3 Wi-Fi CSI should expose acquisition diagnostics because Espressif's implementation specifically supplies RSSI, RF noise floor and reception/control metadata. fileciteturn2file0L1-L10

### Quality representation

Do **not** define one universal `quality = 0.73`.

Use:

```text
quality_class:
  GOOD
  LIMITED
  UNUSABLE

quality_reasons:
  []
```

Optionally preserve sensor-native numeric diagnostics such as SNR, point count, tracking covariance, foreground contrast, packet rate and RF noise floor. Their scales stay sensor-specific.

A feature can update a personal baseline **only when its quality is GOOD**.

LIMITED features can be included in the anomaly evidence packet but should not train normality.

UNUSABLE means:

```json
{
  "value": null,
  "valid": false,
  "missing_reason": "sensor_stale"
}
```

Never `0`, never previous-value fill, never population mean.

**Window coverage hypothesis:** require at least `80%` valid expected samples for a windowed feature to be marked GOOD. This is an **engineering starting hypothesis**, not a research-derived clinical threshold. Sweep 60/70/80/90/95% in replay and select based on false packets, missed anomalies and monitoring availability.

### Robust personal baseline

For every continuous feature/context maintain:

```text
median
MAD
q05
q25
q75
q95
minimum_sensor_resolution_or_scale_floor
eligible_minutes
eligible_days
baseline_window_start
baseline_window_end
baseline_version
source_feature_version
```

Compute:

\[
s_{MAD}=1.4826 \times MAD
\]

and use:

\[
scale=\max(
1.4826 MAD,\;
IQR/1.349,\;
feature\_scale\_floor
)
\]

\[
z_{robust}=\frac{x-\mathrm{median}}{scale}
\]

The MAD is a robust dispersion statistic specifically suited to median-centered comparisons. citeturn25search7 The normal-equivalent constants above are statistical scaling conventions; they do **not** imply the resident's feature distribution is Gaussian.

Store empirical quantiles anyway. They are especially useful when distributions are skewed or bounded.

### Personal context

V1 should maintain:

1. a **resident-global** baseline;
2. a **time-of-day** baseline once mature;
3. a **zone-specific** baseline only where semantically appropriate;
4. no day-of-week authority initially.

**Time-of-day proposal:** four-hour local-time bins with fallback to the global personal baseline.

That four-hour number is an **engineering hypothesis**. Test two-, four- and six-hour bins against false alerts in sleep/reading/daytime activity.

Day-of-week baselines should remain non-authoritative until at least four observations of each weekday are available—approximately four weeks. That minimum is an **engineering hypothesis** designed to prevent a “Tuesday baseline” built from one Tuesday.

### Calibration stages

These are deliberately conservative **engineering starting hypotheses**:

| Stage | Eligibility requirement | Authority |
|---|---|---|
| `BOOTSTRAP` | `<12 eligible resident-hours` | Deterministic safety only; no personalized behavioral event authority |
| `PROVISIONAL` | `≥12 eligible h` across `≥2 calendar days` | Generate anomaly packets; calibration prominently limited |
| `USABLE` | `≥24 eligible h` across `≥3 calendar days` | Personalized anomaly packets may influence normal product policy |
| `MATURE` | `≥72 eligible h` across `≥7 calendar days` | Time-of-day baseline allowed if each context has sufficient coverage |

Do not tune these by window-level accuracy. Tune by **false anomaly packets/day, false caregiver events/day and baseline stability**.

### Baseline horizon

Use a **rolling 14-calendar-day recent-history horizon** for V1 personal behavior summaries, but retain immutable older baseline versions.

This value has supporting transfer evidence from the real-world Minder/CMP work, where 7–14-day thresholding performed best and a two-week baseline was discussed as useful for balancing recent behavioral change against ordinary variability. citeturn20view3

It remains a **transfer hypothesis** for second-level radar/thermal features, not a clinically validated number.

Compare `7 / 14 / 28 days` during Phase 8.

### Baseline update implementation

Do not update per second directly.

Aggregate eligible observations into **one-minute baseline summary records** containing median, IQR, extrema, valid coverage and relevant state occupancy.

Recompute the active rolling baseline every **15 minutes**.

Both values are **engineering hypotheses**. The purpose is to:

- reduce serially correlated samples dominating the baseline;
- make baseline snapshots cheap to version;
- prevent a short burst from immediately redefining normality;
- simplify exact replay.

### Eligibility predicate

An observation enters the learning buffer only if all of these are true:

```text
resident_assigned_to_room
resident_present
single_person_state
monitoring_state == ACTIVE
feature_quality == GOOD
not candidate_anomaly
not active_anomaly
not unresolved_anomaly_guard
not resident_away
not calibration_or_recalibration
sensor_configuration_unchanged
room_configuration_unchanged
no_sensor_degradation_affecting_feature
not within_post_anomaly_guard_period
```

This is where your product rules need to be brutally strict.

A clever anomaly model cannot recover after you teach it that an unresolved abnormal period is “normal.”

### Freeze and post-anomaly guard

Freeze affected baseline features **from the first candidate-anomaly timestamp, not from event creation**.

Keep them frozen through the active episode and for **30 minutes after numerical return to baseline**.

The 30-minute guard is an **engineering starting hypothesis**. Replay `5 / 15 / 30 / 60 min` and measure whether anomaly tails leak into the baseline.

An unresolved caregiver event can keep affected learning frozen even if the numerical anomaly has ended, depending on event family/configuration.

### Sensor or room change

Maintain a dependency map.

```text
radar moved/replaced
  -> invalidate radar position, zone, height, speed, radar-motion baselines
  -> invalidate derived fall geometry calibration

thermal moved/replaced
  -> invalidate thermal centroid, floor geometry, uprightness,
     foreground area and thermal motion baselines

Wi-Fi AP/channel/bandwidth/transmitter/receiver placement changed
  -> invalidate all CSI baselines

material room layout changed
  -> invalidate location/zone and environment-sensitive sensor baselines

resident-room reassignment
  -> create new room-dependent baseline lineage
```

Do not overwrite the old baseline. Create `baseline_v+1` with a reason and parent version.

### Feature-level anomaly thresholding

Production V1 starting thresholds:

```text
moderate deviation: |z_robust| >= 3.0
extreme deviation:  |z_robust| >= 4.0
```

These are **engineering starting hypotheses**, not clinically validated cutoffs.

Why start high? At second-level cadence across many features, low thresholds create a combinatorial false-alert problem. Persistence is still required.

For a feature to become a general anomaly initiator:

```text
same feature is extreme in >= 3 of the last 5 valid 1-s bins
```

or:

```text
two independent sensor/feature groups are each moderate
in >= 3 of the last 5 valid 1-s bins
```

Again, `3/5` is a **starting hypothesis**. Sweep `2/3`, `3/5`, `4/5`, `5/5`.

### Overall anomaly strength

Do not average all features.

Use:

```text
overall_anomaly_strength =
    max(abs(robust_z)) among valid changed numeric features
```

and separately report:

```text
independent_supporting_sensors
supporting_feature_count
contradicting_sensor_count
missing_sensor_count
persistence_seconds
```

This avoids a dangerous outcome where a very strong radar collapse becomes “medium” because CSI is absent.

### Rate and progression

For every continuous changed feature retain:

```text
delta_1s
delta_5s
robust_z
robust_delta_z
direction = UP | DOWN | MIXED
trajectory = RISING | FALLING | SUSTAINED | RECOVERING | OSCILLATING
```

For general behavioral features, estimate five-second rate from the valid normalized frames.

For fall-like behavior, **use source-native vertical velocity and height trajectory**, not the generic five-second derivative.

### Sustained movement

Use a **30-second rolling median activity window**, updated every five seconds.

Trigger the movement-anomaly candidate after three consecutive anomalous evaluations.

That gives approximately `40 s` from a sustained onset before a normal behavioral movement packet becomes active, depending on the initial window.

These are **engineering hypotheses** specifically designed to stop ordinary short bursts from becoming caregiver work.

### Repetitive movement

Use a **60-second analysis window**, updated every 30 seconds, containing:

```text
motion burst intervals
motion-energy autocorrelation / periodicity score
movement direction reversals if available
CSI periodicity support
```

Require two anomalous windows before activation.

This roughly `60–90 s` persistence is a **V1 hypothesis**. Real recordings are mandatory before it acquires caregiver-event authority.

### Inactivity while present

Do not hard-code “10 minutes still = abnormal.”

Use:

```text
time_since_meaningful_motion
versus
resident/time-context baseline distribution
```

Candidate rule:

```text
time_since_meaningful_motion >
max(
    resident_context_q99,
    resident_context_median + 4 * robust_scale
)
```

with an additional `60 s` persistence confirmation.

`q99`, `4×` and `60 s` are **engineering starting hypotheses**. Sleep and quiet reading must be explicitly included in calibration/evaluation.

### Respiration deviation

Only score respiration when radar's respiration-quality gate is GOOD.

Use a **60-second stable respiration estimate** and require two consecutive anomalous windows before generating a respiration-deviation packet.

Those windows are **engineering hypotheses**; they must be replaced/tuned against Mahin's actual radar respiration algorithm.

A respiration anomaly alone should **not create a V1 high/critical caregiver event** without another objective safety signal.

No value is emitted when quality is inadequate.

### Fall-like fast state machine

This should be built before the general anomaly model is entrusted with safety.

State:

```text
STABLE
  -> RAPID_DESCENT
  -> LOW_POSITION
  -> POST_TRANSITION
  -> CONFIRMED_FALL_LIKE or RECOVERED
```

Source evidence supports using short radar windows, vertical dynamics and height collapse: mmFall used one-second radar windows and a 0.6 m height-drop constraint; TI's implementation uses target-height history with a configurable 2.5-second fall buffer and proportional fall threshold. citeturn13view2turn15search13

Do **not** copy either threshold unchanged.

Start Phase 5 simulation with:

```text
transition duration <= 2.0 s

height collapse:
  >= 0.50 m
  OR
  post_height <= 65% of recent stable upright height

plus:
  downward vertical motion evidence

and preferably:
  thermal floor-level / low-body geometry

followed by:
  reduced movement during next 5 s
```

Every numerical value above is an **engineering starting hypothesis** informed by—but intentionally not identical to—the published mmFall/TI references. Test falls, quick sitting, kneeling, controlled descent, picking objects up and lying deliberately on the floor.

**Policy paths**

```text
Radar GOOD + Thermal GOOD + both corroborate
    -> provisional fall-like caregiver event immediately

Radar GOOD + strong multi-feature radar collapse
+ Thermal UNAVAILABLE
+ post-fall low position/stillness
    -> provisional fall-like event, lower confidence
       and normally lower initial priority than corroborated case

Radar suggests fall + Thermal GOOD strongly contradicts
    -> do not average;
       create/continue anomaly evidence;
       invoke interpretation;
       deterministic policy decides from explicit contradiction

possible multiple people
    -> fall-like event may still occur,
       but wording must say resident attribution is uncertain
```

This is essential: **absence of corroboration is not the same as contradictory evidence.**

### Hysteresis

Generic anomaly start:

```text
|z| >= 4.0 persistent
or cross-sensor moderate support
```

Generic anomaly end:

```text
all initiating features |z| < 2.5
for 10 consecutive valid seconds
```

`2.5` and `10 s` are **engineering starting hypotheses**.

If samples become missing during the end condition, the timer stops. Missing data must never be interpreted as recovery.

### Anomaly lifecycle and deduplication

Use:

```text
CANDIDATE
ACTIVE
RECOVERING
CLOSED
```

`CANDIDATE`: abnormal threshold crossed but persistence not met.

`ACTIVE`: persistence rule met; evidence packet created and interpretation eligible.

`RECOVERING`: start threshold no longer met but end hysteresis not yet satisfied.

`CLOSED`: end hysteresis satisfied.

Do not delete the anomaly after closure.

An existing ACTIVE anomaly receives updates rather than new anomaly IDs when:

```text
same resident
same evidence family / materially overlapping feature set
continuous or near-continuous timeline
```

Merge gaps shorter than **60 seconds** for ordinary behavior episodes.

That is an **engineering hypothesis**; tune `30 / 60 / 120 / 300 s`.

A new abnormal period after clear recovery becomes a **new anomaly with `recurrence_of`** rather than reopening the previous anomaly.

### Isolation Forest shadow detector

Train per resident from baseline-eligible feature vectors only.

Start with the mature scikit-learn implementation defaults of `100 trees` and `max_samples=min(256,n)`, while fixing `random_state` so replays are deterministic. Those are implementation defaults/precedents, not product validation. citeturn25search20

Do **not impute absent sensor features** for the model.

For V1 either:

1. operate IF only when a defined fixed feature set is present; or
2. maintain separate shadow models for only the two or three most common modality masks later.

I recommend option one initially.

Threshold its score using a held-out eligible personal-baseline tail rather than granting the library's contamination setting safety authority.

**Starting hypothesis:** flag the top `0.5%` most anomalous eligible-validation scores as the shadow threshold.

Never create an event from IF in Phase 5–7.

Measure:

```text
IF-only anomalies later caregiver-confirmed
transparent-filter anomalies missed by IF
IF false packets/day
score stability after room/sensor changes
```

### EWMA, CUSUM and PELT

Build a small EWMA feature now:

\[
E_t = \alpha z_t + (1-\alpha)E_{t-1}
\]

For sustained motion, use a **30-second half-life** starting hypothesis:

\[
\alpha=1-2^{-1/30}\approx0.0228
\]

This is not a clinical threshold. Store the EWMA in the packet as `sustained_change_score`; initially do not let it create an event independently.

CUSUM should be shadow/research-only until you have enough real normal data to tune average run length and desired detectable shifts.

PELT should run over replay histories—hour/day scale—to detect:

```text
behavior regime changes
sensor relocation signatures
post-recalibration discontinuities
gradual routine shifts
```

PELT's exact penalized segmentation and favorable computational scaling make it appropriate for this kind of retrospective task. citeturn25search9

## Rich anomaly evidence contract and worked examples

The packet should be immutable as a versioned snapshot, while an anomaly episode can have multiple packet revisions.

A key design rule:

> **The LLM receives a compact but evidence-rich representation plus references/tools—not raw radar point clouds, thermal video or CSI streams.**

### Recommended canonical contract

```json
{
  "schema_version": "anomaly-evidence/1.0",
  "anomaly_id": "anom_...",
  "packet_revision": 3,

  "resident_ref": "resident_...",
  "room_ref": "room_...",

  "timing": {
    "candidate_started_at": "2026-08-28T12:00:00.000Z",
    "activated_at": "2026-08-28T12:00:03.000Z",
    "current_time": "2026-08-28T12:00:18.000Z",
    "duration_s": 18,
    "last_normal_before": "2026-08-28T11:59:59.000Z"
  },

  "versions": {
    "filter_version": "filter-1.0.0",
    "config_version": "cfg-clinic-1.3.2",
    "feature_contract_version": "features-1.0",
    "baseline_version": "base_res123_room7_v18",
    "radar_algorithm_version": "radar-sim-0.4",
    "thermal_algorithm_version": "thermal-sim-0.3",
    "csi_algorithm_version": "csi-sim-0.2"
  },

  "calibration": {
    "maturity": "MATURE",
    "eligible_hours": 118.4,
    "eligible_days": 11,
    "baseline_horizon_days": 14,
    "currently_frozen": true,
    "freeze_reasons": ["active_anomaly"]
  },

  "monitoring": {
    "state": "ACTIVE",
    "resident_presence": "PRESENT",
    "possible_multiple_people": false,
    "resident_identity_assumed": false,
    "away_state": false
  },

  "anomaly": {
    "lifecycle_state": "ACTIVE",
    "overall_strength": {
      "value": 6.8,
      "scale": "max_abs_robust_z"
    },
    "progression": "SUSTAINED",
    "initiating_feature_ids": [
      "feat_radar_height",
      "feat_radar_vertical_velocity"
    ],
    "persistence_s": 18
  },

  "changed_features": [
    {
      "feature_id": "feat_example",
      "name": "radar_motion_energy",
      "sensor": "RADAR",
      "current": {
        "value": 0.83,
        "unit": "normalized_source_units",
        "valid": true
      },
      "quality": {
        "class": "GOOD",
        "reasons": []
      },
      "baseline": {
        "context": "resident_global",
        "median": 0.18,
        "mad": 0.06,
        "q05": 0.06,
        "q25": 0.12,
        "q75": 0.26,
        "q95": 0.39,
        "eligible_minutes": 6032
      },
      "deviation": {
        "robust_z": 6.1,
        "direction": "UP",
        "delta_1s": 0.09,
        "delta_5s": 0.51,
        "trajectory": "SUSTAINED"
      },
      "persistence": {
        "abnormal_valid_bins": 16,
        "last_20_valid_bins": 20
      }
    }
  ],

  "time_series": {
    "short": {
      "resolution_s": 1,
      "duration_s": 30,
      "features": {
        "radar_motion_energy": [
          0.17, 0.18, 0.19, 0.41, 0.62, 0.77, 0.81
        ]
      }
    },
    "long": {
      "resolution_s": 30,
      "duration_s": 900,
      "features": {
        "radar_motion_energy_median": [
          0.15, 0.16, 0.18, 0.51
        ]
      }
    }
  },

  "sensors": {
    "radar": {
      "availability": "AVAILABLE",
      "quality": "GOOD",
      "last_sample_age_ms": 82,
      "evidence": {},
      "quality_diagnostics": {}
    },
    "thermal": {
      "availability": "AVAILABLE",
      "quality": "GOOD",
      "last_sample_age_ms": 119,
      "evidence": {},
      "quality_diagnostics": {}
    },
    "wifi_csi": {
      "availability": "AVAILABLE",
      "quality": "LIMITED",
      "last_sample_age_ms": 180,
      "evidence": {},
      "quality_diagnostics": {
        "reason": "packet_rate_below_expected"
      }
    }
  },

  "fusion": {
    "agreements": [],
    "contradictions": [],
    "missing_or_stale": [],
    "independent_supporting_sensors": 2
  },

  "context": {
    "recent_related_anomalies": [],
    "historical_events": [],
    "caregiver_feedback": [],
    "resident_context_refs": [],
    "room_setup_changes": [],
    "device_changes": []
  },

  "trigger": {
    "reason_codes": [
      "PERSISTENT_EXTREME_FEATURE_DEVIATION"
    ],
    "deterministic_safety_triggered": false
  },

  "unknowns": [
    "cause_of_behavior_change"
  ],

  "evidence_refs": [
    {
      "type": "normalized_feature_timeline",
      "ref": "evidence://..."
    },
    {
      "type": "sensor_detail",
      "sensor": "RADAR",
      "ref": "evidence://..."
    }
  ]
}
```

The packet deliberately distinguishes `unknown`, `unavailable`, `limited` and `contradictory`. Those are not interchangeable.

### Strong fall-like evidence

```json
{
  "schema_version": "anomaly-evidence/1.0",
  "anomaly_id": "anom_fall_001",
  "resident_ref": "resident_42",
  "room_ref": "room_7",
  "timing": {
    "candidate_started_at": "2026-08-28T18:41:04.200Z",
    "activated_at": "2026-08-28T18:41:05.100Z",
    "current_time": "2026-08-28T18:41:10.100Z",
    "duration_s": 5.9
  },
  "versions": {
    "filter_version": "1.0.0",
    "config_version": "1.0.0",
    "baseline_version": "base_42_018",
    "feature_contract_version": "1.0"
  },
  "calibration": {
    "maturity": "MATURE",
    "currently_frozen": true,
    "freeze_reasons": ["active_anomaly"]
  },
  "monitoring": {
    "state": "ACTIVE",
    "resident_presence": "PRESENT",
    "possible_multiple_people": false
  },
  "anomaly": {
    "lifecycle_state": "ACTIVE",
    "overall_strength": {
      "value": 9.4,
      "scale": "max_abs_robust_z"
    },
    "progression": "RAPID_TRANSITION_THEN_STILL"
  },
  "changed_features": [
    {
      "name": "radar_height_m",
      "sensor": "RADAR",
      "current": {"value": 0.54, "unit": "m", "valid": true},
      "quality": {"class": "GOOD"},
      "baseline": {
        "context": "recent_stable_upright",
        "median": 1.58,
        "q05": 1.44,
        "q95": 1.69
      },
      "deviation": {
        "delta_1s": -0.78,
        "delta_5s": -1.03,
        "direction": "DOWN",
        "trajectory": "RAPID_DROP"
      }
    },
    {
      "name": "radar_vertical_velocity_mps",
      "sensor": "RADAR",
      "current": {"value": -1.72, "unit": "m/s", "valid": true},
      "quality": {"class": "GOOD"},
      "deviation": {
        "robust_z": -9.4,
        "direction": "DOWN"
      }
    },
    {
      "name": "thermal_floor_proximity",
      "sensor": "THERMAL",
      "current": {"value": 0.91, "unit": "score", "valid": true},
      "quality": {"class": "GOOD"},
      "deviation": {
        "direction": "UP",
        "trajectory": "NEW_LOW_POSTURE"
      }
    }
  ],
  "time_series": {
    "short": {
      "resolution_ms": 100,
      "duration_s": 4,
      "summary": "upright -> rapid descent -> low position"
    },
    "long": {
      "resolution_s": 30,
      "duration_s": 900,
      "summary": "ordinary movement before transition"
    }
  },
  "sensors": {
    "radar": {
      "availability": "AVAILABLE",
      "quality": "GOOD",
      "evidence": {
        "stable_track_pre_transition": true,
        "height_collapse_m": 1.03,
        "post_transition_motion": "LOW"
      }
    },
    "thermal": {
      "availability": "AVAILABLE",
      "quality": "GOOD",
      "evidence": {
        "pre_posture": "UPRIGHT_LIKE",
        "post_posture": "FLOOR_LEVEL_LIKE"
      }
    },
    "wifi_csi": {
      "availability": "AVAILABLE",
      "quality": "GOOD",
      "evidence": {
        "brief_motion_burst": true,
        "post_transition_motion": "LOW"
      }
    }
  },
  "fusion": {
    "agreements": [
      "RADAR_AND_THERMAL_SUPPORT_RAPID_VERTICAL_TRANSITION",
      "RADAR_AND_THERMAL_SUPPORT_LOW_POST_POSITION"
    ],
    "contradictions": [],
    "missing_or_stale": [],
    "independent_supporting_sensors": 3
  },
  "context": {
    "recent_related_anomalies": [],
    "historical_events": [],
    "caregiver_feedback": []
  },
  "trigger": {
    "deterministic_safety_triggered": true,
    "reason_codes": [
      "RAPID_DESCENT",
      "HEIGHT_COLLAPSE",
      "THERMAL_FLOOR_CORROBORATION"
    ]
  },
  "unknowns": [
    "whether_the_transition_was_accidental",
    "medical_cause"
  ],
  "evidence_refs": [
    {"type": "fall_transition_timeline", "ref": "evidence://fall/001"}
  ]
}
```

The deterministic product may already create a generic **fall-like** event before the LLM returns.

### Persistent unexplained movement anomaly

```json
{
  "schema_version": "anomaly-evidence/1.0",
  "anomaly_id": "anom_move_014",
  "resident_ref": "resident_42",
  "room_ref": "room_7",
  "timing": {
    "candidate_started_at": "2026-08-28T20:12:00Z",
    "activated_at": "2026-08-28T20:12:40Z",
    "current_time": "2026-08-28T20:17:00Z",
    "duration_s": 300
  },
  "versions": {
    "filter_version": "1.0.0",
    "config_version": "1.0.0",
    "baseline_version": "base_42_018"
  },
  "calibration": {
    "maturity": "MATURE",
    "currently_frozen": true
  },
  "monitoring": {
    "state": "ACTIVE",
    "resident_presence": "PRESENT",
    "possible_multiple_people": false
  },
  "anomaly": {
    "lifecycle_state": "ACTIVE",
    "overall_strength": {"value": 6.2, "scale": "max_abs_robust_z"},
    "progression": "SUSTAINED"
  },
  "changed_features": [
    {
      "name": "radar_motion_energy",
      "sensor": "RADAR",
      "current": {"value": 0.79, "unit": "normalized", "valid": true},
      "quality": {"class": "GOOD"},
      "baseline": {
        "median": 0.21,
        "mad": 0.063,
        "q95": 0.39
      },
      "deviation": {
        "robust_z": 6.2,
        "direction": "UP",
        "trajectory": "SUSTAINED"
      }
    },
    {
      "name": "thermal_motion_energy",
      "sensor": "THERMAL",
      "current": {"value": 0.66, "unit": "normalized", "valid": true},
      "quality": {"class": "GOOD"},
      "baseline": {"median": 0.19, "q95": 0.37},
      "deviation": {
        "robust_z": 5.1,
        "direction": "UP"
      }
    }
  ],
  "time_series": {
    "short": {
      "resolution_s": 1,
      "duration_s": 60,
      "summary": "continuous elevated motion without major position change"
    },
    "long": {
      "resolution_s": 30,
      "duration_s": 900,
      "summary": "movement rose abruptly and remained elevated"
    }
  },
  "sensors": {
    "radar": {"availability": "AVAILABLE", "quality": "GOOD"},
    "thermal": {"availability": "AVAILABLE", "quality": "GOOD"},
    "wifi_csi": {
      "availability": "AVAILABLE",
      "quality": "GOOD",
      "evidence": {"motion_index": "ELEVATED"}
    }
  },
  "fusion": {
    "agreements": ["THREE_SENSORS_SUPPORT_ELEVATED_MOVEMENT"],
    "contradictions": [],
    "missing_or_stale": [],
    "independent_supporting_sensors": 3
  },
  "context": {
    "recent_related_anomalies": [],
    "historical_events": []
  },
  "trigger": {
    "deterministic_safety_triggered": false,
    "reason_codes": ["PERSISTENT_MOVEMENT_DEVIATION"]
  },
  "unknowns": [
    "objective_behavior_category",
    "reason_for_increased_movement"
  ],
  "evidence_refs": [
    {"type": "movement_timeline", "ref": "evidence://movement/014"}
  ]
}
```

### One sensor unavailable

```json
{
  "schema_version": "anomaly-evidence/1.0",
  "anomaly_id": "anom_missing_003",
  "resident_ref": "resident_42",
  "room_ref": "room_7",
  "timing": {
    "candidate_started_at": "2026-08-28T21:05:00Z",
    "activated_at": "2026-08-28T21:05:40Z",
    "current_time": "2026-08-28T21:07:00Z",
    "duration_s": 120
  },
  "versions": {
    "filter_version": "1.0.0",
    "config_version": "1.0.0",
    "baseline_version": "base_42_018"
  },
  "calibration": {
    "maturity": "MATURE",
    "currently_frozen": true
  },
  "monitoring": {
    "state": "LIMITED",
    "resident_presence": "PRESENT",
    "possible_multiple_people": false
  },
  "anomaly": {
    "lifecycle_state": "ACTIVE",
    "overall_strength": {"value": 5.4, "scale": "max_abs_robust_z"},
    "progression": "SUSTAINED"
  },
  "changed_features": [
    {
      "name": "radar_motion_energy",
      "sensor": "RADAR",
      "current": {"value": 0.72, "valid": true},
      "quality": {"class": "GOOD"},
      "baseline": {"median": 0.20, "q95": 0.38},
      "deviation": {"robust_z": 5.4, "direction": "UP"}
    }
  ],
  "time_series": {
    "short": {"resolution_s": 1, "duration_s": 60},
    "long": {"resolution_s": 30, "duration_s": 900}
  },
  "sensors": {
    "radar": {"availability": "AVAILABLE", "quality": "GOOD"},
    "thermal": {
      "availability": "UNAVAILABLE",
      "quality": "UNUSABLE",
      "last_sample_age_ms": 94000,
      "missing_reason": "DEVICE_OFFLINE"
    },
    "wifi_csi": {"availability": "AVAILABLE", "quality": "GOOD"}
  },
  "fusion": {
    "agreements": ["RADAR_AND_CSI_SUPPORT_MOVEMENT_CHANGE"],
    "contradictions": [],
    "missing_or_stale": ["THERMAL"],
    "independent_supporting_sensors": 2
  },
  "context": {
    "device_changes": [],
    "recent_related_anomalies": []
  },
  "trigger": {
    "deterministic_safety_triggered": false,
    "reason_codes": ["PERSISTENT_MOVEMENT_DEVIATION"]
  },
  "unknowns": [
    "thermal_posture_evidence"
  ],
  "evidence_refs": [
    {"type": "monitoring_quality", "ref": "evidence://quality/003"}
  ]
}
```

Nothing substitutes a thermal value.

### Sensors disagreeing

```json
{
  "schema_version": "anomaly-evidence/1.0",
  "anomaly_id": "anom_disagree_007",
  "resident_ref": "resident_42",
  "room_ref": "room_7",
  "timing": {
    "candidate_started_at": "2026-08-28T21:40:04Z",
    "activated_at": "2026-08-28T21:40:06Z",
    "current_time": "2026-08-28T21:40:11Z",
    "duration_s": 7
  },
  "versions": {
    "filter_version": "1.0.0",
    "config_version": "1.0.0",
    "baseline_version": "base_42_018"
  },
  "calibration": {
    "maturity": "MATURE",
    "currently_frozen": true
  },
  "monitoring": {
    "state": "ACTIVE",
    "resident_presence": "PRESENT",
    "possible_multiple_people": false
  },
  "anomaly": {
    "lifecycle_state": "ACTIVE",
    "overall_strength": {"value": 7.1, "scale": "max_abs_robust_z"},
    "progression": "CONFLICTING"
  },
  "changed_features": [
    {
      "name": "radar_height_m",
      "sensor": "RADAR",
      "current": {"value": 0.58, "unit": "m", "valid": true},
      "quality": {"class": "GOOD"},
      "deviation": {"robust_z": -7.1, "direction": "DOWN"}
    },
    {
      "name": "thermal_uprightness",
      "sensor": "THERMAL",
      "current": {"value": 0.83, "valid": true},
      "quality": {"class": "GOOD"},
      "deviation": {"direction": "UNCHANGED_UPRIGHT_LIKE"}
    }
  ],
  "time_series": {
    "short": {"resolution_s": 1, "duration_s": 30},
    "long": {"resolution_s": 30, "duration_s": 600}
  },
  "sensors": {
    "radar": {
      "availability": "AVAILABLE",
      "quality": "GOOD",
      "evidence": {"height_collapse": true}
    },
    "thermal": {
      "availability": "AVAILABLE",
      "quality": "GOOD",
      "evidence": {"floor_level_posture": false}
    },
    "wifi_csi": {
      "availability": "AVAILABLE",
      "quality": "LIMITED"
    }
  },
  "fusion": {
    "agreements": [],
    "contradictions": [
      {
        "code": "RADAR_LOW_HEIGHT_THERMAL_UPRIGHT",
        "severity": "MATERIAL"
      }
    ],
    "missing_or_stale": [],
    "independent_supporting_sensors": 1
  },
  "context": {},
  "trigger": {
    "deterministic_safety_triggered": false,
    "reason_codes": ["EXTREME_RADAR_VERTICAL_DEVIATION"]
  },
  "unknowns": [
    "whether_radar_track_switched_or_fragmented",
    "true_posture"
  ],
  "evidence_refs": [
    {"type": "cross_sensor_timeline", "ref": "evidence://disagreement/007"}
  ]
}
```

The correct response is not “average to medium confidence.” It is **explicit contradiction**.

### Monitoring degradation initially resembling resident change

```json
{
  "schema_version": "anomaly-evidence/1.0",
  "anomaly_id": "anom_quality_011",
  "resident_ref": "resident_42",
  "room_ref": "room_7",
  "timing": {
    "candidate_started_at": "2026-08-28T22:10:00Z",
    "activated_at": "2026-08-28T22:10:05Z",
    "current_time": "2026-08-28T22:11:00Z",
    "duration_s": 60
  },
  "versions": {
    "filter_version": "1.0.0",
    "config_version": "1.0.0",
    "baseline_version": "base_42_018"
  },
  "calibration": {
    "maturity": "MATURE",
    "currently_frozen": true,
    "freeze_reasons": ["sensor_degradation"]
  },
  "monitoring": {
    "state": "DEGRADED",
    "resident_presence": "UNKNOWN",
    "possible_multiple_people": false
  },
  "anomaly": {
    "lifecycle_state": "ACTIVE",
    "overall_strength": {
      "value": null,
      "scale": "not_computed_due_to_invalid_source"
    },
    "progression": "RECLASSIFIED_AS_MONITORING_DEGRADATION"
  },
  "changed_features": [],
  "time_series": {
    "short": {
      "resolution_s": 1,
      "duration_s": 60,
      "summary": "radar values became exactly constant while thermal continued to show movement"
    },
    "long": {"resolution_s": 30, "duration_s": 900}
  },
  "sensors": {
    "radar": {
      "availability": "AVAILABLE_BUT_INVALID",
      "quality": "UNUSABLE",
      "evidence": {
        "identical_sample_run_s": 58,
        "sequence_counter_advancing": true
      },
      "quality_reasons": ["FROZEN_VALUES"]
    },
    "thermal": {
      "availability": "AVAILABLE",
      "quality": "GOOD",
      "evidence": {"movement_detected": true}
    },
    "wifi_csi": {
      "availability": "AVAILABLE",
      "quality": "GOOD"
    }
  },
  "fusion": {
    "agreements": [],
    "contradictions": [
      "RADAR_REPORTS_NO_CHANGE_WHILE_THERMAL_AND_CSI_CHANGE"
    ],
    "missing_or_stale": [],
    "independent_supporting_sensors": 2
  },
  "context": {
    "device_changes": []
  },
  "trigger": {
    "deterministic_safety_triggered": false,
    "reason_codes": ["SENSOR_FROZEN_VALUES"]
  },
  "unknowns": [
    "resident_motion_during_invalid_radar_period"
  ],
  "evidence_refs": [
    {"type": "sensor_quality_trace", "ref": "evidence://quality/011"}
  ]
}
```

This should normally create/update **monitoring degraded**, not “prolonged inactivity.”

### Repeated anomaly resembling a caregiver-confirmed event

```json
{
  "schema_version": "anomaly-evidence/1.0",
  "anomaly_id": "anom_repeat_022",
  "resident_ref": "resident_42",
  "room_ref": "room_7",
  "timing": {
    "candidate_started_at": "2026-08-29T00:14:00Z",
    "activated_at": "2026-08-29T00:14:45Z",
    "current_time": "2026-08-29T00:17:00Z",
    "duration_s": 180
  },
  "versions": {
    "filter_version": "1.0.0",
    "config_version": "1.0.0",
    "baseline_version": "base_42_018"
  },
  "calibration": {
    "maturity": "MATURE",
    "currently_frozen": true
  },
  "monitoring": {
    "state": "ACTIVE",
    "resident_presence": "PRESENT",
    "possible_multiple_people": false
  },
  "anomaly": {
    "lifecycle_state": "ACTIVE",
    "overall_strength": {"value": 5.8, "scale": "max_abs_robust_z"},
    "progression": "SUSTAINED",
    "numerical_similarity": {
      "similar_anomaly_id": "anom_009",
      "similarity_basis": [
        "same_features",
        "similar_duration",
        "similar_time_of_day",
        "similar_zone"
      ]
    }
  },
  "changed_features": [
    {
      "name": "repetition_score",
      "sensor": "RADAR",
      "current": {"value": 0.88, "valid": true},
      "quality": {"class": "GOOD"},
      "baseline": {"median": 0.21, "q95": 0.47},
      "deviation": {"robust_z": 5.8, "direction": "UP"}
    }
  ],
  "time_series": {
    "short": {"resolution_s": 1, "duration_s": 120},
    "long": {"resolution_s": 30, "duration_s": 1800}
  },
  "sensors": {
    "radar": {"availability": "AVAILABLE", "quality": "GOOD"},
    "thermal": {"availability": "AVAILABLE", "quality": "GOOD"},
    "wifi_csi": {"availability": "AVAILABLE", "quality": "GOOD"}
  },
  "fusion": {
    "agreements": [
      "RADAR_THERMAL_CSI_SUPPORT_REPETITIVE_MOVEMENT"
    ],
    "contradictions": [],
    "missing_or_stale": []
  },
  "context": {
    "recent_related_anomalies": [
      {"anomaly_id": "anom_009"}
    ],
    "historical_events": [
      {
        "event_id": "event_188",
        "relation": "numerically_similar",
        "resolved": true
      }
    ],
    "caregiver_feedback": [
      {
        "event_id": "event_188",
        "label": "confirmed_objective_pattern",
        "text": "Repeated movement was present when checked."
      }
    ]
  },
  "trigger": {
    "deterministic_safety_triggered": false,
    "reason_codes": [
      "PERSISTENT_REPETITION_DEVIATION",
      "SIMILAR_TO_PRIOR_CONFIRMED_EVENT"
    ]
  },
  "unknowns": [
    "cause_of_repeated_behavior"
  ],
  "evidence_refs": [
    {"type": "similarity_comparison", "ref": "evidence://similarity/022"}
  ]
}
```

The historical event can influence interpretation. It **must not silently lower the production threshold**.

### Incomplete personal calibration

```json
{
  "schema_version": "anomaly-evidence/1.0",
  "anomaly_id": "anom_cal_004",
  "resident_ref": "resident_new",
  "room_ref": "room_12",
  "timing": {
    "candidate_started_at": "2026-08-29T02:00:00Z",
    "activated_at": "2026-08-29T02:00:40Z",
    "current_time": "2026-08-29T02:02:00Z",
    "duration_s": 120
  },
  "versions": {
    "filter_version": "1.0.0",
    "config_version": "1.0.0",
    "baseline_version": "base_new_003"
  },
  "calibration": {
    "maturity": "PROVISIONAL",
    "eligible_hours": 15.2,
    "eligible_days": 2,
    "currently_frozen": true,
    "limitations": [
      "insufficient_history_for_time_of_day_baseline"
    ]
  },
  "monitoring": {
    "state": "ACTIVE",
    "resident_presence": "PRESENT",
    "possible_multiple_people": false
  },
  "anomaly": {
    "lifecycle_state": "ACTIVE",
    "overall_strength": {"value": 4.7, "scale": "max_abs_robust_z"},
    "progression": "SUSTAINED"
  },
  "changed_features": [
    {
      "name": "radar_motion_energy",
      "sensor": "RADAR",
      "current": {"value": 0.70, "valid": true},
      "quality": {"class": "GOOD"},
      "baseline": {
        "context": "resident_global_provisional",
        "median": 0.26,
        "q95": 0.44,
        "reliability": "LIMITED"
      },
      "deviation": {"robust_z": 4.7, "direction": "UP"}
    }
  ],
  "time_series": {
    "short": {"resolution_s": 1, "duration_s": 60},
    "long": {"resolution_s": 30, "duration_s": 900}
  },
  "sensors": {
    "radar": {"availability": "AVAILABLE", "quality": "GOOD"},
    "thermal": {"availability": "AVAILABLE", "quality": "GOOD"},
    "wifi_csi": {"availability": "AVAILABLE", "quality": "GOOD"}
  },
  "fusion": {
    "agreements": ["MULTIPLE_SENSORS_SUPPORT_MOVEMENT"],
    "contradictions": [],
    "missing_or_stale": []
  },
  "context": {},
  "trigger": {
    "deterministic_safety_triggered": false,
    "reason_codes": ["PROVISIONAL_BASELINE_DEVIATION"]
  },
  "unknowns": [
    "whether_this_is_unusual_for_this_time_of_day"
  ],
  "evidence_refs": [
    {"type": "calibration_history", "ref": "evidence://calibration/004"}
  ]
}
```

The LLM may interpret it, but policy should be conservative because the resident baseline itself is immature.

### Possible multiple-person presence

```json
{
  "schema_version": "anomaly-evidence/1.0",
  "anomaly_id": "anom_multi_006",
  "resident_ref": "resident_42",
  "room_ref": "room_7",
  "timing": {
    "candidate_started_at": "2026-08-29T03:10:00Z",
    "activated_at": "2026-08-29T03:10:05Z",
    "current_time": "2026-08-29T03:12:00Z",
    "duration_s": 120
  },
  "versions": {
    "filter_version": "1.0.0",
    "config_version": "1.0.0",
    "baseline_version": "base_42_018"
  },
  "calibration": {
    "maturity": "MATURE",
    "currently_frozen": true,
    "freeze_reasons": ["possible_multiple_people"]
  },
  "monitoring": {
    "state": "LIMITED",
    "resident_presence": "POSSIBLY_PRESENT",
    "possible_multiple_people": true,
    "resident_identity_assumed": false
  },
  "anomaly": {
    "lifecycle_state": "ACTIVE",
    "overall_strength": {"value": 5.0, "scale": "max_abs_robust_z"},
    "progression": "ATTRIBUTION_LIMITED"
  },
  "changed_features": [
    {
      "name": "thermal_person_count_hint",
      "sensor": "THERMAL",
      "current": {"value": 2, "valid": true},
      "quality": {"class": "GOOD"},
      "deviation": {"direction": "MULTIPLE_PERSON_EVIDENCE"}
    },
    {
      "name": "radar_track_count",
      "sensor": "RADAR",
      "current": {"value": 2, "valid": true},
      "quality": {"class": "GOOD"},
      "deviation": {"direction": "MULTIPLE_PERSON_EVIDENCE"}
    }
  ],
  "time_series": {
    "short": {"resolution_s": 1, "duration_s": 60},
    "long": {"resolution_s": 30, "duration_s": 900}
  },
  "sensors": {
    "radar": {
      "availability": "AVAILABLE",
      "quality": "GOOD",
      "evidence": {"track_count": 2}
    },
    "thermal": {
      "availability": "AVAILABLE",
      "quality": "GOOD",
      "evidence": {"person_count_hint": 2}
    },
    "wifi_csi": {
      "availability": "AVAILABLE",
      "quality": "GOOD",
      "evidence": {"activity_increased": true}
    }
  },
  "fusion": {
    "agreements": [
      "RADAR_AND_THERMAL_SUPPORT_MULTIPLE_PEOPLE"
    ],
    "contradictions": [],
    "missing_or_stale": []
  },
  "context": {
    "resident_specific_learning_paused": true
  },
  "trigger": {
    "deterministic_safety_triggered": false,
    "reason_codes": ["POSSIBLE_MULTIPLE_PEOPLE"]
  },
  "unknowns": [
    "which_track_is_the_assigned_resident",
    "which_person_generated_observed_movement"
  ],
  "evidence_refs": [
    {"type": "occupancy_timeline", "ref": "evidence://occupancy/006"}
  ]
}
```

This is exactly where the product must resist the temptation to “guess which one is the resident.”

## LLM interpretation, skills and deterministic safety policy

### Recommended V1 architecture

Use **one primary structured interpretation call with read-only retrieval tools and versioned skill instructions**.

Do **not** make ten sequential LLM calls because you have ten conceptual skills.

The skills should be separately versioned instruction modules, assembled into one interpretation context.

This preserves:

```text
one interpretation transaction
one retrieval log
one structured output
one model/version record
one deterministic validation step
```

LLM tool-use research such as ReAct supports the general architectural idea that reasoning can be interleaved with targeted retrieval rather than stuffing all potentially relevant information into the initial context. citeturn26search2turn26search22 This evidence supports the **tool pattern**, not the safety of LLM medical interpretation.

### Skill contract

| Skill | Responsibility | Required input | May retrieve | Required output | Explicitly prohibited | Failure fallback |
|---|---|---|---|---|---|---|
| **Evidence inspection** | Establish exactly what is observed | Evidence packet | Detailed feature timeline | Evidence IDs and factual observations | Inventing measurement, replacing nulls | Mark evidence insufficient |
| **Context retrieval** | Determine whether additional history is relevant | Packet + anomaly timing | Longer timeline, baseline history, setup/device changes | Retrieval summary with refs | Unbounded fishing; altering data | Continue with provided packet |
| **Pattern classification** | Select objective category or unknown | Evidence + retrieved context | Similar anomalies/events | `objective_category` | Diagnosing disease or cause | `UNKNOWN_ANOMALY` |
| **Alternative ranking** | Enumerate plausible non-diagnostic explanations | Evidence | Prior similar objective patterns | Ranked alternatives | Medication/disease attribution without supplied context/evidence | Return none/unknown |
| **Contradiction check** | Search for evidence inconsistent with leading interpretation | Leading interpretation + all sensor evidence | Cross-sensor timeline | Contradiction IDs | Ignoring contradictory sensor because confidence is high | Lower interpretation confidence |
| **Uncertainty check** | Identify missing/limited calibration and modalities | Packet quality/context | Quality history | Missing-information list | Fabricating certainty | `LOW` confidence |
| **Repeated-pattern analysis** | Compare with prior numerical episodes | Current anomaly | Prior anomalies/events/feedback | Similarity references | Treating similarity as proof of same cause | “Similar objective pattern” only |
| **Response recommendation** | Recommend product-level response class | Interpretation | Current policy context read-only | no-action / observe / awareness / caregiver-event recommendation | Directly executing safety action | Deterministic policy decides |
| **Caregiver wording** | Convert evidence into concise objective wording | Validated interpretation | None normally | Plain-English explanation | Diagnosis, causal certainty, unsourced values | Template-based generic explanation |
| **Structured-output validation** | Ensure semantic references are traceable | Draft output | None | Valid schema + referenced evidence IDs | Adding new factual claims | Reject output and fall back |

Record for every run:

```json
{
  "model_provider": "...",
  "model_id": "...",
  "model_snapshot_or_version": "...",
  "skill_bundle_version": "interpretation-skills-1.3.0",
  "prompt_template_version": "interp-prompt-1.1",
  "tool_contract_version": "monitoring-read-tools-1.0",
  "output_schema_version": "interpretation-output-1.0",
  "retrieved_refs": [],
  "invocation_id": "..."
}
```

### LLM read-only tools

Expose narrow functions such as:

```text
get_anomaly_timeline(anomaly_id, before_s, after_s, resolution)
get_feature_timeline(anomaly_id, feature_names, ...)
get_baseline_history(resident_ref, feature_names, ...)
find_similar_anomalies(resident_ref, anomaly_id, limit)
get_related_events(resident_ref, ...)
get_caregiver_feedback(event_ids)
get_resident_context(resident_ref, permitted_fields)
get_sensor_quality_history(room_ref, sensors, ...)
get_room_setup_changes(room_ref, ...)
get_device_changes(room_ref, ...)
```

Every result should carry provenance and timestamps.

Do not expose arbitrary database queries.

Do not expose write tools.

Do not expose raw continuous radar ADC, raw continuous thermal streams or full CSI matrices.

### Structured interpretation output

```json
{
  "schema_version": "interpretation/1.0",

  "objective_category": {
    "value": "FALL_LIKE_TRANSITION",
    "supported": true
  },

  "ranked_alternatives": [
    {
      "label": "CONTROLLED_DESCENT_OR_INTENTIONAL_FLOOR_MOVEMENT",
      "rank": 1,
      "supporting_evidence_ids": [],
      "contradicting_evidence_ids": []
    }
  ],

  "interpretation_confidence": {
    "level": "HIGH",
    "basis": [
      "radar and thermal independently support rapid downward transition"
    ]
  },

  "supporting_evidence_ids": [
    "feat_radar_height",
    "feat_radar_vertical_velocity",
    "thermal_floor_posture"
  ],

  "contradictory_evidence": [],

  "missing_information": [
    "intent_of_movement"
  ],

  "more_observation_needed": false,

  "recommended_product_action": "CAREGIVER_EVENT",

  "caregiver_facing_wording":
    "A rapid downward movement was detected, followed by a low floor-level posture and reduced movement.",

  "unsupported_statements": [
    "The resident fainted.",
    "The resident had a medical emergency."
  ]
}
```

I would use an **ordinal interpretation confidence** (`LOW / MEDIUM / HIGH`) in V1 rather than manufacture a pseudo-probability such as `0.87`. A probability becomes meaningful only after calibration against a substantial labeled corpus.

### One call versus multiple calls

| Architecture | Reliability | Cost/latency | Auditability | Recommendation |
|---|---:|---:|---:|---|
| One unconstrained prose call | Poor | Lowest | Poor | Reject |
| One structured call, full packet only | Good for simple episodes | Low | Good | Acceptable baseline |
| **One structured call + read-only retrieval** | **Best V1 tradeoff** | Low–medium | **High** | **Build** |
| Ten sequential “skills” | Potentially better decomposition, but error propagation | High | Complex | Do not build V1 |
| Interpreter + second independent LLM reviewer on every anomaly | Some additional error detection | Roughly doubles interpretation work | Good but expensive | Not justified universally |
| **Interpreter + deterministic contradiction validator + conditional second reviewer** | Strong practical compromise | Added cost only on selected cases | High | **Recommended later/limited V1** |

### Is a second contradiction-review LLM worth it?

**Not on every anomaly.**

There is insufficient monitoring-domain evidence to justify doubling LLM calls universally, and a second call from a similar model is not truly independent in the statistical sense.

Instead, run a deterministic validator on **every** output:

```text
all claimed measurements exist
all evidence IDs exist
no null value is described as measured
no diagnosis language
recommended action is allowed enum
LLM did not downgrade deterministic safety trigger
contradictions in packet are represented
calibration limitation is represented
multiple-person attribution limitation is represented
```

Invoke a second contradiction-review model only when, for example:

```text
proposed caregiver priority is high/critical
AND sensor contradiction exists

OR

LLM says HIGH confidence
AND only one independent sensor supports interpretation

OR

multiple-person state exists
AND LLM attributes behavior specifically to resident

OR

deterministic safety result and LLM interpretation materially disagree
```

Those conditions are **engineering policy proposals**, not research-validated thresholds.

### LLM unavailable fallback

The system must remain useful without an LLM:

```text
anomaly filter
  -> deterministic product policy
  -> generic objective event/awareness wording
```

Examples:

**Fall fallback**

> “Fall-like movement detected: rapid downward movement and low-position evidence were observed. Automated interpretation is currently unavailable.”

**Movement fallback**

> “Movement has remained substantially above this resident's recent baseline for 5 minutes.”

**Inactivity fallback**

> “The resident appears present and has remained still longer than their recent pattern for this time period.”

**Degraded fallback**

> “Monitoring is limited because the thermal sensor is unavailable.”

Those templates should be generated from stored evidence fields, not free-form LLM output.

### Deterministic policy ordering

Policy should evaluate in this order:

```text
system/data integrity
    ↓
presence / away / multiple-person restrictions
    ↓
deterministic safety triggers
    ↓
anomaly strength + persistence + calibration
    ↓
LLM interpretation
    ↓
policy validation
    ↓
no action / continue observing / awareness / caregiver event
```

That ordering prevents an LLM from saying “probably intentional” and suppressing a physically strong fall trigger.

Confidence and priority remain orthogonal:

```text
high-confidence + low-priority:
  "resident left room"

low-confidence + potentially high-priority:
  "radar strongly suggests a fall but thermal is unavailable"

high-confidence + high-priority:
  "rapid collapse corroborated by radar and thermal, low position follows"
```

## Simulator-first evaluation, hardware validation and operational metrics

Simulation is extremely valuable here—but only for the parts simulation can actually falsify.

Tanaka et al. is particularly relevant because it shows that a simulator can exercise different abnormal behaviors at radically different timescales, but the authors also explicitly make the validity of results conditional on simulator realism. citeturn27search0 Mertens similarly injected controlled subtle deviations into synthetic daily patterns to evaluate a simple personalized detector. citeturn27search6

That is exactly how Phase 5 should be treated: **software/control-logic validation, not sensor-performance validation.**

### Simulator scenario matrix

| Scenario | What simulator should verify | Can Phase 5 meaningfully validate it? | What later requires real recordings? |
|---|---|---:|---|
| Ordinary daytime movement | No persistent anomaly; baseline eligible | **Yes** | Actual feature distribution |
| Quiet reading | Long low movement can remain normal for that resident/context | **Yes** logically | Real radar/thermal micro-motion behavior |
| Sleep | Baseline handles long inactivity/time context | **Yes** | Real posture/respiration/multipath |
| Long stillness while present | Adaptive inactivity threshold; packet at intended point | **Yes** | Actual false-alert rate |
| Resident leaving | Away awareness, not anomaly/emergency; learning freezes | **Yes** | Sensor exit accuracy |
| Resident returning | Monitoring reestablishes before learning resumes | **Yes** | Track reacquisition behavior |
| Visitor entering | Multiple-person state; resident learning stops | **Yes** | Real multi-person detection accuracy |
| Possible multiple people | Attribution unknown; no identity guessing | **Yes** | Occlusion/crossing tracks |
| Quick sitting | Fall rule must reject | **Yes**, with synthetic separability assumptions | **Critical real test** |
| Controlled descent | Reject or lower confidence compared with fall | **Yes** logically | **Critical real test** |
| Kneeling | Avoid fall event | **Yes** | **Critical real test** |
| Picking object up | Height reduction without fall progression | **Yes** | **Critical real test** |
| Fall-like movement | Fast safety state machine activates | **Yes** | Real sensitivity/specificity |
| Remain on floor | Event updates rather than duplicates; persistent low posture | **Yes** | Real sensor coverage |
| Repetitive movement | Correct persistence and grouping | **Yes** | Real periodicity extraction |
| Unusually high activity | 30-s sustained window behavior | **Yes** | Real threshold distribution |
| Respiration change | Quality gating, persistence and null handling | **Yes** logically | **Absolutely requires real/reference recordings** |
| Gradual routine change | Baseline adaptation versus anomaly freeze | **Yes** | Longitudinal field recordings |
| One missing sensor | No imputation; confidence/context changes | **Yes** | Recovery patterns |
| Stale measurement | Staleness detected before behavioral inference | **Yes** | Hardware timing behavior |
| Delayed measurement | Event-time alignment and out-of-order rules | **Yes** | Network jitter distributions |
| Sensor disagreement | Contradiction retained | **Yes** | Real disagreement frequencies |
| Frozen values | System degradation instead of inactivity | **Yes** | Device failure signatures |
| Moved sensor | Configuration version change, baseline invalidation | **Yes** | Automatic movement detection |
| Sensor replacement | Selective recalibration | **Yes** | Replacement-to-replacement offsets |
| Room-layout change | Room-dependent baselines invalidated | **Yes** | Which physical changes materially affect each sensor |
| Wi-Fi channel change | CSI quality/config invalidation; no resident anomaly | **Yes** | Magnitude of real CSI shift |
| Recurring anomaly | New anomaly/event linked to previous episode | **Yes** | Similarity feature calibration |
| Unresolved anomaly | Baseline remains frozen | **Yes** | Workflow behavior in deployment |
| LLM unavailable | Deterministic system still functions | **Yes** | Provider outage behavior |
| LLM unsupported explanation | Validator rejects causal/measurement invention | **Yes** | Real adversarial/error-rate testing |

### Simulator design

Generate ground-truth latent states first:

```text
resident_presence
person_count
position
posture
movement_level
vertical_motion
repetitive_behavior
respiration
room_configuration
sensor_configuration
```

Then independently generate **sensor observations** from those states.

Do not have the simulator directly emit perfectly consistent final features all the time. It needs controlled imperfection:

```text
noise
bias
dropout
staleness
out-of-order delivery
clock offset
contradiction
track switching
quantization
frozen values
gradual drift
configuration change
```

Otherwise you are testing your own assumptions against themselves.

### Property-based tests

In addition to scenario examples, encode invariants:

```text
Missing input never becomes a numeric feature.
UNUSABLE features never update baseline.
Possible-multiple-person periods never update resident baseline.
Away periods never update resident baseline.
Active anomaly periods never update affected baseline.
Replaying identical evidence + versions produces identical anomaly lifecycle.
Changing only LLM output cannot suppress a deterministic safety event.
An anomaly end cannot occur solely because samples became missing.
A sensor failure cannot silently become normal resident behavior.
Room/sensor change creates a new baseline lineage.
```

Those are some of the highest-value Phase 5 tests because simulation can prove them exactly.

### Replay reproducibility

Persist enough to reconstruct every decision:

```text
normalized observations
quality results
alignment decisions
room/context state
baseline snapshot/version
filter version
configuration version
feature extractor version
random seed for any randomized shadow detector
anomaly packet revisions
LLM input packet
tool retrieval results/references
model + skill versions
LLM structured output
policy version
final product action
```

For deterministic components, replay must produce byte-equivalent or canonical-JSON-equivalent results.

### Operational success measurements

Rank metrics in this order:

| Metric | Definition |
|---|---|
| **False caregiver events / monitored resident-day** | Incorrect caregiver events divided by days with usable monitoring |
| **Meaningful anomalies missed** | Ground-truth relevant scenarios with no appropriate packet/event |
| **False anomaly packets / monitored resident-day** | Interpretation workload before policy suppression |
| **Detection delay** | Ground-truth anomaly onset → candidate, active packet and caregiver event; report p50/p90/p95 |
| **Duplicate-event rate** | Multiple caregiver events produced for one ground-truth episode |
| **Event-duration error** | Difference between ground-truth episode and detected start/end |
| **Baseline contamination** | Ineligible observations present in baseline storage; software target should be **exactly zero** |
| **Monitoring-state fractions** | Time in full / limited / unavailable |
| **Sensor-failure recovery** | Time from restored good data to valid monitoring state |
| **Configuration-change recovery** | Time from movement/replacement/layout change to calibrated authority |
| **LLM evidence-support rate** | Interpretive factual claims with explicit packet/retrieval support |
| **Unsupported-claim rate** | Claims failing deterministic evidence validation; safety target should be **zero released unsupported claims** |
| **Explanation usefulness** | Caregiver-rated clarity/actionability |
| **Replay reproducibility** | Same stored input/version → same deterministic result; target **100%** |

The `0` and `100%` values above are **software integrity requirements**, not clinical-performance claims.

Do not establish a fake V1 target such as “<0.1 false alerts/day” before real recordings. The literature is too heterogeneous to justify it.

Instead, Phase 8 should produce an empirical operating curve:

```text
threshold / persistence configuration
    versus
false packets per resident-day
false caregiver events per resident-day
missed meaningful anomalies
p95 detection delay
time monitoring limited
```

Then select the operating point with caregivers.

### Hardware-validation plan

**Radar**

Capture:

```text
frame timestamp
track ID
track quality/confidence/covariance if available
point count / selected point-cloud descriptors
x/y/z
height estimate
horizontal and vertical velocity
activity/motion measure
micro-motion/vital-sign quality
respiration estimate or null
configuration hash
```

Validate against staged recordings for:

```text
walk
sit
quick sit
kneel
bend/pick-up
lie down intentionally
controlled descent
falls in different directions
floor recovery
occlusion
blankets
bed/chair geometry
two people
track crossing
sensor movement
```

mmFall demonstrates why body-size and room-layout diversity matter: its two similar participants and relatively simple room are explicit limitations. citeturn14view0turn13view2

**Thermal**

During development preserve raw calibrated 32×24 temperatures plus:

```text
ambient/sensor temperature metadata where available
frame timestamp
foreground/background mask
person detection(s)
centroid
geometry/posture features
background model version
quality
```

Test:

```text
sunlight
heater/radiator
warm bedding
cold/warm room transition
person close/far
partial body
two people
empty room
large warm objects
sensor moved
```

Background maintenance is not optional: MLX90640 research showed a major person-detection gain from explicit background subtraction, but its assumptions must be adapted to occupied care rooms. citeturn3view0

**Wi-Fi CSI**

Preserve during development:

```text
CSI amplitudes/phase representation needed by algorithm
channel
bandwidth
AP/transmitter identity
receiver identity
RSSI
RF noise floor
packet/reception timestamp
packet rate
firmware/config version
antenna configuration
```

Espressif exposes these types of acquisition metadata and explicitly supports ESP32-S3. fileciteturn2file0L1-L10

Test:

```text
channel change
AP reboot
router replacement
transmitter movement
receiver movement
furniture movement
door state
visitor
multiple people
ordinary network traffic
packet-rate reduction
interference
```

A Wi-Fi environment change should first hit `csi_environment_shift` / quality, not `resident_behavior_changed`.

### Heart and respiration

The research reviewed supports keeping your existing stance.

Radar-based respiration has enough manufacturer/reference and research support to justify experimental/product feature development when signal quality is explicit. TI currently provides vital-sign reference material for its radar platform. citeturn15search3turn15search9

But the exact implementation openness and reliability constraints vary, and TI support documentation illustrates that vital-sign operation has practical stabilization/configuration constraints and source-access limitations. citeturn15search6turn15search25

Therefore:

```text
respiration:
  V1 experimental anomaly feature after quality validation

radar heart rate:
  store/evaluate experimentally
  no safety authority until independently validated

Wi-Fi heart rate:
  no caregiver-facing authority in V1

quality insufficient:
  value = null
```

## Build decisions, datasets, licensing and remaining uncertainty

### Build now

**Production**

```text
normalized feature contract
timestamp/quality validation
GOOD / LIMITED / UNUSABLE feature status
no-imputation semantics
one-second behavior frames
source-rate fast safety lane
personal median/MAD/IQR/quantile baseline
14-day baseline lineage
strict baseline eligibility/freeze rules
time-of-day fallback hierarchy
robust feature deviation
persistence
hysteresis
episode lifecycle
deduplication/recurrence
event-specific sensor agreement/contradiction
possible-multiple-person freeze
monitoring degradation detector
deterministic fall-like state machine
rich evidence packet
one structured retrieval-capable LLM interpreter
deterministic semantic/output validator
LLM-unavailable templates
immutable version/replay records
```

### Build but keep shadowed

```text
Isolation Forest personal challenger
EWMA sustained-change score initially without independent event authority
CUSUM experiments
similar-anomaly numerical retrieval
conditional second LLM contradiction reviewer
```

### Build offline/replay-only

```text
PELT regime/change-point analysis
baseline-horizon comparisons
threshold sweeps
anomaly clustering
feedback replay experiments
```

### Postpone

```text
end-to-end multimodal neural anomaly model
autoencoder/transformer production authority
learned multimodal fusion embeddings
LLM-direct safety control
automatic threshold adaptation from caregiver feedback
day-of-week production personalization before adequate history
Wi-Fi-based 3-D localization
Wi-Fi heart-rate decisions
radar heart-rate caregiver decisions
diagnostic labels
causal medical explanations
conformal safety guarantees
```

Isolation Forest is attractive precisely because it gives you a cheap learned comparator without forcing these postponed architectural commitments; the original method was designed as a computationally efficient anomaly detector. citeturn25search0

### Public resources with highest immediate value

**TI Radar Toolbox / IWR6843 references.** Best source for the future radar producer contract, people tracks, height and vital-sign reference behavior. The Radar Toolbox remains a current supported TI package, with recent releases after the earlier research. citeturn15search2turn15search7

**EAVISE MLDetection thermal dataset/work.** Best implementation lesson for thermal foreground/background handling and MCU-scale low-resolution person detection. citeturn3view0

**InfoLab-SKKU Thermal-Human-Detection.** Small but directly usable MLX90640 code/data repository, MIT licensed. citeturn27search3 fileciteturn4file0L1-L10

**eHomeSeniors.** Useful staged low-resolution thermal fall corpus, particularly for seeing posture/trajectory diversity. It should not be your sole fall benchmark because of staged participants and limited subject count. citeturn22search0turn24search3

**Taramasco multimodal fall dataset.** Particularly valuable because it combines 60–64 GHz radar and thermal sensing in synchronized staged falls—the closest available sensor pairing to your planned stack among sources located. citeturn17search0turn17search2

**MM-Fi.** Valuable for stress-testing the hardware-neutral feature interface and cross-modal research; not an operational anomaly benchmark. citeturn26search0

**Widar3.0.** Valuable for CSI preprocessing/domain-generalization research and as a warning that environment/location/orientation are fundamental wireless-sensing variables. citeturn26search1turn26search5

**Espressif ESP-CSI.** This should be Mahin's primary implementation starting point for ESP32-S3 CSI acquisition rather than reproducing low-level CSI extraction from academic papers. The repository is currently Apache-2.0 and had activity in 2026. fileciteturn1file0L1-L10

**Mertens/MoBaDDD.** Useful conceptual comparator for “how simple can personalized anomaly detection be?” Its recent-history majority reference and Hamming-distance deviation are simple enough to reproduce exactly. citeturn27search19turn27search6

**Minder Contextual Matrix Profile study.** Best evidence found for operational anomaly evaluation over thousands of real monitored patient-days. citeturn20view3

### Licensing concerns

Licensing needs more discipline than “the dataset is downloadable.”

**Espressif `esp-csi` is Apache-2.0**, which is comparatively straightforward for commercial code reuse subject to its license conditions. fileciteturn1file0L1-L10

**InfoLab-SKKU Thermal-Human-Detection is MIT licensed.** fileciteturn4file0L1-L10

**The MM-Fi GitHub repository currently exposes no detected repository license.** That means you should not assume the code can be incorporated into a commercial codebase merely because it is public. Treat it as reference-only until the authors' intended software/data terms are confirmed. fileciteturn3file0L1-L10

**Taramasco's publication is distributed under a non-commercial Creative Commons form in the accessible article copy.** Do not infer from the paper license that every dataset artifact has identical rights; confirm the archive's dataset-specific terms before commercial model development. citeturn17search1

**eHomeSeniors' publication/data are public research resources, but dataset-specific downstream commercial-use terms should be verified from the actual download agreement before putting it into a commercial training pipeline.** The paper's accessibility alone is not a software/data license. citeturn22search0turn19search4

**TI software must be treated under the license shipped with the corresponding SDK/Radar Toolbox component.** “Free,” “reference implementation” or “source available” does not automatically mean arbitrary redistribution is permitted. TI's current product pages distinguish its SDK/tool packages and versions, while some vital-sign source has additional access restrictions. citeturn15search2turn15search25

For Phase 5, the cleanest path is therefore:

```text
implement your own anomaly/persistence/baseline code
under your own repository/license;

use permissively licensed sensor reference code where appropriate;

use restrictive/unclear datasets for evaluation only
until commercial-use rights are confirmed.
```

### The uncertainties that actually matter

**Fall thresholds remain hardware- and placement-dependent.** Neither the mmFall 0.6 m threshold nor TI's reference settings are defensible as your finished threshold. citeturn13view2turn15search13

**Radar track-height quality in bedrooms has to be measured.** Beds, furniture, blankets, partial occlusion and mounting height may fundamentally change the reliability of “height collapse.”

**Thermal multiple-person detection at 32×24 may become a major gating factor.** The resolution is sufficient for useful person detection, but occluding or close people can defeat clean person separation; the available thermal literature does not establish your required resident-attribution reliability. citeturn3view0turn22search0

**CSI may contribute less than expected once radar and thermal are present.** That is not a failure. If real Phase 8 results show CSI rarely changes policy decisions but significantly increases degradation states and calibration complexity, cut its authority rather than forcing it to justify the hardware.

**Two weeks may be correct for routine change and wrong for high-frequency kinematics.** The evidence for 7–14 days comes from home-activity monitoring, not radar vertical velocity. citeturn20view3 Maintain separate baseline versioning so this can be changed feature-family by feature-family.

**Caregiver feedback will become extremely valuable, but using it online too early would create a hidden reinforcement loop.** Your existing decision to store feedback, replay it and only change released versions is correct.

**Unknown anomaly must remain common enough to be honest.** An LLM forced into categories will manufacture semantics your sensors never measured.

### Concrete Phase 5 implementation order

The fastest defensible route is:

**First:** implement the normalized feature/quality contract, baseline eligibility predicate and deterministic replay/version machinery.

**Second:** implement Candidate A with global resident median/MAD/IQR/quantiles and no time-of-day specialization.

**Third:** implement the anomaly lifecycle, persistence, hysteresis, merging and recurrence.

**Fourth:** add multiple-person/away/degraded system conditions and prove with tests that none can contaminate learning.

**Fifth:** build the fall-like deterministic fast state machine.

**Sixth:** add mature/time-of-day baselines and feature-specific movement, inactivity, repetition and respiration windows.

**Seventh:** build the rich anomaly evidence packet and retrieval API.

**Eighth:** add one structured LLM interpretation call and deterministic semantic validator.

**Ninth:** enable Isolation Forest in shadow mode and EWMA progression fields.

**Tenth:** replay the entire simulator matrix while optimizing operational metrics—not window classification accuracy.

This ordering matters. Starting with Isolation Forest or the LLM before baseline eligibility and sensor-quality semantics are airtight would be solving the interesting problem before the important one.

### Direct primary-source links

1. **mmFall — fall detection with mmWave radar:** [arXiv paper](https://arxiv.org/abs/2003.02386)

2. **TI Radar Toolbox:** [TI Radar Toolbox / Developer Zone](https://dev.ti.com/tirex/explore)

3. **TI mmWave SDK:** [TI MMWAVE-SDK](https://www.ti.com/tool/MMWAVE-SDK)

4. **TI mmWave Studio / ADC capture:** [TI MMWAVE-STUDIO](https://www.ti.com/tool/MMWAVE-STUDIO)

5. **EAVISE low-resolution thermal person detection:** [arXiv](https://arxiv.org/abs/2205.03969)

6. **eHomeSeniors:** [Sensors paper](https://www.mdpi.com/1424-8220/19/20/4565)

7. **Taramasco multimodal fall dataset:** [PeerJ/PMC article](https://pmc.ncbi.nlm.nih.gov/articles/PMC11970414/)

8. **MM-Fi paper:** [arXiv](https://arxiv.org/abs/2305.10345)

9. **MM-Fi author repository:** [GitHub](https://github.com/ybhbingo/MMFi_dataset)

10. **Widar3.0 project:** [Tsinghua project page](https://tns.thss.tsinghua.edu.cn/widar3.0/)

11. **Espressif ESP-CSI:** [GitHub](https://github.com/espressif/esp-csi)

12. **InfoLab-SKKU MLX90640 thermal implementation:** [GitHub](https://github.com/InfoLab-SKKU/Thermal-Human-Detection)

13. **Mertens et al., Motion Sensor-Based Detection of Outlier Days:** [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC8472855/)

14. **Bijlani et al., Contextual Matrix Profile anomaly monitoring:** [JMIR Aging](https://aging.jmir.org/2022/3/e38211/)

15. **PRISM personalized in-home anomaly detection:** [arXiv](https://arxiv.org/abs/2212.14736)

16. **Tanaka et al., simulator-based long-term abnormal behavior detection:** [arXiv](https://arxiv.org/abs/2411.13153)

17. **Isolation Forest:** [IEEE original paper](https://ieeexplore.ieee.org/document/4781136)

18. **Isolation Forest maintained implementation:** [scikit-learn](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.IsolationForest.html)

19. **PELT original paper:** [arXiv](https://arxiv.org/abs/1101.1438)

20. **ReAct tool/retrieval architecture:** [arXiv](https://arxiv.org/abs/2210.03629)

The final V1 decision is therefore:

> **Build a transparent per-resident robust-baseline anomaly engine as the production filter. Preserve per-sensor quality and contradictions rather than collapsing them into one score. Use deterministic fast state machines for fall-like safety evidence. Add persistence, hysteresis and immutable episodes before any LLM. Give one structured LLM interpreter read-only retrieval tools, then place a deterministic policy/validator after it. Run Isolation Forest in shadow mode, EWMA as sustained-change evidence, PELT offline, and postpone complex learned multimodal models until continuous real-room recordings demonstrate that the transparent system has a specific, measurable failure they can solve.**

That is the simplest architecture I found that is simultaneously defensible, reproducible, simulator-first, compatible with your eventual radar/thermal/CSI stack, honest about missing and conflicting evidence, resistant to baseline poisoning, and upgradeable without touching the caregiver workflow.