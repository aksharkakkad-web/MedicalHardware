
Designing a Defensible V1 Contactless Monitoring and Anomaly-Detection System
Executive summary and assumptions
The strongest V1 is not a single multimodal neural network and it is not a system that forces all three sensors into one global confidence score. The defensible architecture is a quality-gated, event-specific late-fusion system:

mmWave radar should provide the strongest evidence for geometry, motion, range/velocity, falls, immobility, and respiration; MLX90640 thermal should provide independent evidence for occupancy, coarse body geometry, vertical position, floor-level posture, and motion; ESP32-S3 CSI should provide an inexpensive, privacy-preserving corroborating channel for motion, presence, repetitive activity, and potentially respiration. Radar cardiac measurements should remain experimental in V1, while CSI-based heart rate should not influence caregiver-facing decisions at all. TI's IWR6843-class 60–64 GHz hardware has on-chip radar DSP/HWA and supports range/velocity/angle processing; MLX90640 provides a 32×24 temperature array up to 64 Hz; and ESP32-S3 exposes per-subcarrier complex CSI plus reception metadata. 

The intelligence stack should therefore be:

sensor-specific preprocessing → explicit quality/availability → synchronized observations → event-specific evidence → personal baseline deviation → persistence/hysteresis → episode manager → caregiver event

That choice is an engineering inference from the modalities' very different information content and failure modes, and from the fact that the underlying hardware already supports substantial modality-specific preprocessing. It also matches the product constraint in your project brief that bad data should reduce monitoring confidence rather than create artificial certainty, that baseline learning must stop during ambiguous conditions, and that confidence must remain conceptually separate from event priority. 
 

The V1 anomaly layer should use robust median/MAD baselines plus bounded EWMA and explicit duration/state rules. Median absolute deviation is a robust alternative to standard deviation, while EWMA is specifically suited to detecting small sustained shifts that individual observations miss. Isolation Forest is reasonable as a shadow-mode multivariate unknown-anomaly detector after enough clean resident data exists, but should not be the primary V1 event generator. PELT/change-point analysis is useful offline or on longer time horizons. Autoencoders should be postponed: their added data and validation burden is substantial, and even the original MemAE work notes the failure mode where ordinary autoencoders reconstruct anomalies too well. 

Contactless respiration is considerably more credible than contactless heart rate. Radar HR is physically feasible, but the gap between “a cardiac component is measurable” and “continuous HR is trustworthy in a real occupied room” is large. Pi-ViMo, using a TI IWR6843-class radar, reported average HR errors of 11.9% for stationary subjects and 13.6% with micro-level random body movements despite a sophisticated physiology-informed pipeline. That is useful research evidence, but it is not a basis for an HR-only caregiver alert. 

The critical product lesson is blunt: do not spend the three-month MVP trying to beat papers on activity-classification accuracy. Spend it proving that the system knows when it does not know, that event episodes do not spam the user, that calibration cannot poison itself, and that a fall-like candidate remains reproducible from stored objective evidence. Public datasets can bootstrap signal processing, but none is a substitute for recordings in your actual rooms, with your exact placement and hardware. CSI is especially environment-dependent because it directly measures the radio channel, and even major CSI datasets explicitly represent room, position and orientation domains. 

Assumptions. Because the exact radar board, room dimensions, mounting geometry, privacy policy, and resident behavior are unspecified, this report uses a TI IWR6843/IWR6843AOP-class 60-GHz FMCW radar as the concrete radar reference and assumes roughly bedroom/living-room-sized indoor spaces with one assigned resident. Numerical thresholds proposed below are engineering starting configurations, not clinically validated constants. Exact range/angular resolution, frame cadence and vital-sign performance must be re-derived if a different radar is selected. TI's current IWR6843 is a 60–64 GHz, 4-RX/3-TX device with a 200-MHz Cortex-R4F, 600-MHz C67x DSP, radar HWA and about 1.75 MB internal RAM, which makes substantial radar preprocessing on the sensor realistic. 

Sensor contracts, preprocessing, and realistic capabilities
The first architectural decision is the telemetry boundary. Throwing away too much at the sensor is a mistake because it prevents future algorithms from being improved; continuously uploading everything is also a mistake for radar because raw ADC data is orders of magnitude heavier than point clouds or tracks. The correct boundary is different for each modality. TI explicitly supports on-chip FFT/filtering/CFAR processing and raw ADC access through separate high-speed tooling, whereas MLX90640 frames are tiny and ESP32 CSI values are already compact subcarrier measurements. 

Modality	Native/raw information	Recommended V1 acquisition	Recommended transmitted observation	Spatial / temporal meaning	V1 preprocessing	Relative compute
60-GHz mmWave	Complex radar ADC samples across chirps/RX channels; derived range-Doppler/angle data. TI IWR6843 has 4 RX and 3 TX with onboard DSP/HWA. 
Configure roughly 10–20 radar frames/s for room monitoring; retain the exact chirp/frame configuration in metadata. A TI vital-sign reference configuration uses a 90-ms frame period, illustrating an approximately 11-Hz operating point. 
Point cloud {x,y,z,radial_v,SNR/noise}, tracked target state, target count, track quality, occupancy state, motion energy; plus selected complex phase/range-bin signals for respiration/experimental HR. Keep short raw-ADC debug captures, not continuous upload.	True range and Doppler dimensions; angular resolution depends strongly on antenna/configuration. The cited TI vital-sign setup reports ~8.4-cm range resolution for its specific 1.78-GHz bandwidth and ~14.5° azimuth resolution, not universal radar limits. 
Calibration → range FFT → static-clutter suppression → Doppler/CFAR → angle estimation → point cloud → tracking; separate chest/range-bin phase path for vitals.	Highest edge compute, but hardware is designed for it.
MLX90640	768 thermopile pixels, internal RAM/auxiliary calibration data, converted to object temperatures by driver calculations. The device is 32×24, I²C, with 0.5–64-Hz programmable refresh. 
8–16 Hz. Sixteen Hz has precedent in eHomeSeniors; going to 64 Hz buys little for posture/fall monitoring and increases thermal noise. 
Prefer the entire 32×24 compensated temperature frame plus ambient/sensor temperature, bad-pixel status, frame ID and quality. Also derive blob centroid, bbox, area, temperature statistics, vertical extent and frame-to-frame motion.	32×24 spatial grid; FOV options are 55°×35° and 110°×75°. It gives coarse shape/position, not identity-grade imagery. 
Factory calibration/temperature conversion → defective-pixel handling → temporal smoothing → adaptive background/foreground segmentation → blobs/tracks → coarse posture/motion features.	Low; full frames are cheap enough to preserve.
ESP32-S3 CSI	Per-packet complex channel-frequency response. Each subcarrier response is two signed bytes, imaginary then real; available fields can include LLTF, HT-LTF and STBC-HT-LTF. Reception metadata includes RF/network information. 
CSI is packet-driven rather than a fixed-rate sensor. Start with a controlled ~100 packets/s engineering configuration and experimentally sweep lower/higher packet rates; store actual packet timing rather than pretending it is uniformly sampled.	Raw complex CSI vector, packet timestamp/sequence, RSSI, noise floor, channel/bandwidth/MCS/antenna and validity flags. Derive amplitude, differential/conjugate phase, motion energy, spectral bands and quality downstream.	No direct pixel-like spatial resolution from a single Wi-Fi link. Spatial changes are encoded indirectly through multipath across time/subcarriers. Multiple links are required for stronger localization. This follows directly from CSI being a measurement of channel frequency response. 
Callback only validates/copies to ring buffer or queue; later task/backend performs phase handling, subcarrier normalization, filtering, PCA/SVD if useful, STFT/FFT and motion/respiration feature extraction.	Low capture compute; low-to-moderate DSP downstream.

Radar: what it can legitimately do
Radar is the highest-information modality in this stack. An IWR6843-class FMCW radar can generate range, radial velocity, angle and point-cloud/tracking data, and TI reference designs use the family for occupancy/people tracking. The hardware's integrated radar accelerator is explicitly designed for FFT, filtering and CFAR, so transmitting raw ADC to your backend just to redo routine radar DSP would be architectural waste. 

For V1, the radar processor should expose objective observations, not semantic diagnoses: number of tracks, position, centroid/height proxy, velocity, acceleration, vertical displacement, point-cloud spread, motion energy, time-since-meaningful-motion, and track confidence. A separate micro-motion path should preserve the complex signal around a stable target's chest/range cells so that respiration and later cardiac algorithms are replaceable without touching the event workflow. Research systems such as Pi-ViMo explicitly improve vital-sign estimation by combining multiple body scattering points rather than trusting one fixed range bin, reinforcing the value of preserving richer phase evidence. 

Realistic radar failure modes are multipath/reflections, low-SNR target geometry, angular ambiguity, weak separation of nearby people, track switching, furniture/metal-induced ghosts, stationary-target loss if clutter suppression is too aggressive, poor chest orientation for micro-motion, and large-body-motion contamination of vitals. Radar can therefore be excellent at fall kinematics while simultaneously being unusable for HR in the same interval. That is why “radar quality = 0.83” is too crude; quality must be objective-specific. The motion sensitivity documented by Pi-ViMo's markedly worse vital-sign errors under random body movements is direct evidence for this separation. 

Thermal: more useful than its resolution suggests
MLX90640 is genuinely low resolution—768 pixels—but that is enough to preserve useful body-scale geometry. eHomeSeniors recorded MLX90640 at about 16 fps, wall-mounted at 1.2 m, with falls occurring 1–5 m away; its public CSVs contain the 768 temperature values and additional raw sensor information. That makes the sensor highly relevant for coarse posture, centroid trajectory and floor-level confirmation, even though it cannot provide ordinary visual detail. 

The EAVISE MLDetection dataset adds an important complementary result: 32×24 MLX90640 data were collected in offices, laboratories and residential rooms with ceiling-mounted sensors at 90° and 45°, specifically for person detection. The authors also demonstrated a sub-10k-parameter person detector reaching up to 91.62% F1 and running in tens of milliseconds on modest STM32 MCUs. That does not prove your occupancy detector will achieve the same performance, but it does show that useful semantic preprocessing at this resolution does not demand a GPU. 

Thermal's main failures are not ordinary darkness—FIR does not depend on visible illumination—but low body/background thermal contrast, hot radiators/heaters/sun-warmed surfaces, field-of-view clipping, furniture/blanket occlusion, overlapping people, and environmental drift. A thermal blob can also split or merge as posture changes. eHomeSeniors itself notes the value of future tests with obstacles and other heat sources, highlighting the gap between staged datasets and furnished homes. 

Do not discard the 32×24 frame simply to save bandwidth. A raw 16-bit 32×24 frame is only about 1.5 kB; at 16 Hz that is roughly 24.6 kB/s before protocol overhead. Even a float32 compensated array is only about 49 kB/s. Those are arithmetic estimates from the 768-pixel sensor size and recommended cadence; bandwidth is therefore a weak reason to destroy the image. Privacy/storage policy can be a reason, but in an MVP the frames are extremely valuable for debugging segmentation and building your own dataset. The MLX90640's low native resolution already substantially limits personally identifying visual detail compared with conventional imaging. 

CSI: useful corroboration, dangerous to overclaim
ESP32-S3 CSI should be treated as a radio-channel sensor, not as a cheap radar substitute. Espressif defines CSI as the frequency response of Wi-Fi subcarriers estimated when packets are received. The official esp-csi project demonstrates human presence/activity sensing and notes sensitivity to subtle activity such as breathing; it also explicitly warns that test results can be affected by other people in the environment. 

That means CSI is well suited to movement/no-movement, occupancy corroboration, repetitive motion, coarse activity-change evidence, and experimental respiration, but a single link should not be asked for stable 3-D person localization. Its failure modes are exactly the variables that change the radio channel: moved furniture, doors, fans, pets, people outside the intended subject, router/AP changes, Wi-Fi channel or bandwidth changes, antenna orientation, packet-rate jitter, reconnects, multiperson superposition and environmental layout changes. Widar3.0 explicitly encodes room, position and orientation as different sensing domains, which is strong practical evidence that cross-domain variation is a first-order CSI problem. 

Espressif also warns that the CSI callback executes in the Wi-Fi task and should not perform lengthy processing; data should be posted to a queue and handled elsewhere. So the correct ESP32 design is capture quickly, validate metadata, enqueue, then process in a lower-priority task or backend. Do not put PCA, spectrogram construction or neural inference directly in the callback. 

Edge/backend split, bandwidth, and data-quality architecture
The edge/backend boundary should follow one rule:

Do irreversible transformations at the edge only when the raw stream is impractically large or the transformation is deterministic and well understood.

That pushes conventional radar DSP to the radar, leaves thermal frames largely intact, and preserves CSI vectors while moving heavier time-series processing out of the Wi-Fi callback. This is also a privacy win because the highest-rate radar stream does not leave the device, while the two lower-bandwidth modalities can retain enough information for audit and model iteration. TI's radar architecture, the small MLX90640 frame size, and Espressif's callback guidance make this split natural. 

Processing step	Radar	Thermal	CSI	Where V1 should run it	Why
Packet/frame integrity, sequence numbers, timestamps	Yes	Yes	Yes	Edge/gateway	Must happen before network/backend ambiguity.
Sensor calibration / deterministic conversion	Yes	Yes	Minimal	Edge	Sensor-specific and deterministic. MLX90640 requires its calibration data to convert measurements to temperatures. 
FFT / CFAR / angle processing	Yes	No	No	Radar edge	IWR6843 has dedicated DSP/HWA; raw radar streaming is unnecessary for production. 
Thermal temperature frame	No	Yes	No	Preserve	Tiny bandwidth; useful for debugging and future algorithms. 
CSI ring buffering	No	No	Yes	ESP32 edge	Wi-Fi callback should stay short. 
CSI PCA/STFT/long-window filtering	No	No	Yes	Gateway/backend initially	Algorithm still likely to change; preserve source vector.
Tracking / short-window features	Yes	Yes	Optional	Edge or gateway	Reduces traffic and creates normalized observations.
Cross-sensor synchronization	All	All	All	Gateway/backend	Requires shared context.
Personal baseline	All	All	All	Backend	Needs multi-day resident history and freeze logic.
Event-specific fusion	All	All	All	Backend	Needs quality, context and other modalities.
Episode persistence / alerts	All	All	All	Backend	Centralized, auditable policy.
Raw/debug retention	Event snippets	Frames	CSI snippets	Local/backend bounded store	Needed to reproduce false positives without storing everything forever.

For radar, continuous raw ADC is qualitatively different from point-cloud telemetry. TI exposes raw ADC over LVDS through tools such as DCA1000, while production radar processing can run on the embedded HWA/DSP. A representative TI vital-sign configuration has 96 samples/chirp, 288 chirps/frame and four receivers; even before protocol overhead, a full complex raw cube at roughly 11 frames/s is on the order of tens of megabits per second, depending on the exact ADC packing. That is useful for laboratory captures, not an intelligent V1 production contract. 

For CSI, the opposite is true. Each subcarrier is only two signed bytes, and even hundreds of packet observations per second remain modest compared with radar ADC. The real cost is not network capacity but storage volume, synchronization, and downstream processing. During MVP development, retaining raw CSI around events is therefore more valuable than prematurely reducing it to one “movement score.” 

A quality vector, not one quality number
Each observation should carry:

{sensor_id, sensor_time, gateway_time, sequence, schema_version, config_version, quality_components, usable_for[], payload}.

The important field is usable_for[]. For example:

Modality	Quality dimensions V1 should expose	Consequence
Radar	frame continuity; target SNR/noise; track age/stability; target count; point count; residual clutter; target inside validated range/FOV; micro-motion coherence; mounting/config state	A radar observation may be usable_for=fall,motion but not usable_for=respiration,heart_rate.
Thermal	frame age; I²C/read errors; bad-pixel count; ambient drift; hot-background fraction; body/blob contrast; FOV clipping; blob count; segmentation stability	Low contrast can disable posture while preserving a weak occupancy observation. MLX90640 can have defective pixels that must be handled from calibration information. 
CSI	packet cadence/jitter; missing packets; RSSI/noise floor; channel/bandwidth/MCS stability; antenna; valid CSI length; first-word-validity flag; reconnect/channel change; subcarrier coherence	Channel/config changes should trigger recalibration or a quality penalty rather than look like resident anomalies. ESP-IDF exposes the relevant CSI and reception metadata and documents a hardware first-word validity condition. 

Never forward-fill a stale measurement into an event decision. Give every modality an objective-specific time-to-live. If thermal disappears for three seconds, the system has “no current thermal evidence,” not “the last body was still lying on the floor.” This is an architectural recommendation rather than a literature result, but it follows directly from the project's requirement that missing data reduce certainty rather than silently become evidence. 

Likewise, do not impute conflicting modalities into agreement. If radar detects one moving target but thermal reports two warm blobs, the correct state may be occupancy_ambiguous; it is not an invitation to average “1” and “2.” If multiple people are plausible, personal-baseline updates should freeze and resident-specific physiological interpretation should become unavailable. That is especially important for CSI because one wireless link naturally mixes the effects of multiple moving bodies. 
 

A practical confidence model is therefore:

[ C_e = C_{\text{evidence},e} \times C_{\text{quality},e} \times C_{\text{coverage},e} \times C_{\text{context},e} ]

where each term is event-specific. Priority is separate. A high-priority fall candidate from one excellent radar modality can have only moderate confidence because thermal is offline; a low-priority long-term routine change can have very high confidence. Conflating those dimensions is a product mistake.

Event-specific fusion, baselines, anomaly detection, and episode policy
A single global formula such as “50% radar + 30% thermal + 20% CSI” is technically indefensible because the sensors do not measure interchangeable quantities. Radar has direct kinematics; thermal has coarse spatial heat geometry; CSI measures perturbation of a multipath communications channel. Fusion should therefore be late, event-specific and quality-gated. 

For an event (e) and eligible modality (m), it is reasonable to maintain a normalized evidence score (s_{e,m}) and objective-specific quality (q_{e,m}). A quality-weighted score such as

[ S_e = \frac{\sum_{m \in A_e} w_{e,m}q_{e,m}s_{e,m}} {\sum_{m \in A_e} w_{e,m}q_{e,m}} ]

is useful after logical eligibility gates, but the (w_{e,m}) must be event-specific and learned/tuned from hardware data. For safety-critical events such as falls, V1 should rely more heavily on interpretable conjunction/state rules than on a weighted average.

Event family	Primary evidence	Corroborating / disambiguating evidence	Recommended V1 fusion and rule
Presence / away	Radar target/tracking + thermal human blob	CSI motion/presence response	Use radar and thermal as independent primary modalities. Agreement gives strong evidence. One modality alone can support presence with reduced confidence. CSI alone should support only coarse possible_presence unless validated strongly in your placement.
Fall-like episode	Radar: rapid downward/vertical centroid change, velocity/acceleration, point-cloud height collapse	Thermal: fast centroid/vertical-extent drop followed by body-like heat near floor; CSI: abrupt broadband motion then stillness	State machine, not classifier-only: pre-event upright/active → rapid transition → floor-level/low-height evidence → post-transition reduced movement. Strong radar + thermal confirmation is preferred; if one modality is unavailable, require a stronger surviving signal and explicitly lower confidence. eHomeSeniors demonstrates visible thermal geometry changes between standing/fallen states; mmFall similarly coupled an anomaly spike with centroid-height decline rather than using anomaly alone. 
Inactivity while present	Radar track/presence with low macro-motion	Thermal stable blob/centroid; CSI low movement energy	First establish presence. Then measure time-since-meaningful-motion relative to that resident/time context. Never equate “no motion signal” directly with inactivity because it may be away, sensor failure or occlusion.
Repetitive / unusually elevated movement	Radar motion energy/velocity distribution; CSI time-frequency variance	Thermal centroid path / bbox motion	Compare rolling movement features against the resident's own time-context baseline; require persistence. CSI is useful because it is highly sensitive to environmental movement, but that same sensitivity makes quality checks essential. 
Respiration change	Radar phase/micro-motion from a stable target	CSI respiration-band evidence when link quality and single-person context are good	Radar should dominate. Compare rate, spectral concentration and motion contamination with a personal rest baseline. Thermal contributes context/occupancy, not a respiration measurement.
Heart-rate candidate	Radar cardiac micro-motion	CSI only experimental corroboration	No production event in V1. See HR section below.
Unknown anomaly	Robust deviations from normalized features across available modalities	All modalities with event-specific quality	Combine deviation evidence, not semantic labels. Output unknown_anomaly with a list of changed objective features and sensor support.
Monitoring degraded	Sensor-health/quality layer	Cross-modal disagreement	Treat as a system state, not a resident anomaly. Persistent loss can create a device/monitoring notification, but never masquerade as a health event.

The right V1 anomaly stack
The personal baseline should begin with transparent statistics. NIST defines MAD as the median absolute deviation from the median and notes its use as a robust alternative to standard deviation; that robustness is desirable because a resident's ordinary monitoring history will contain occasional abrupt movements and sensor artifacts. 

For a feature (x), use a robust standardized deviation such as

[ z_\text{robust}
\frac{0.6745(x-\operatorname{median}(x))} {\max(\operatorname{MAD}(x),\epsilon)} ]

with an engineering floor (\epsilon) reflecting sensor/feature noise. Do not interpret this as a Gaussian medical z-score; it is simply a normalized resident-relative deviation. The scaling convention comes from the normal-distribution relationship documented by NIST. 

Then maintain a separate bounded EWMA of important normalized features or deviation scores:

[ E_t=\lambda x_t+(1-\lambda)E_{t-1} ]

because EWMA incorporates prior observations with exponentially decreasing weight and is specifically useful for small, gradual shifts. Critically, pause the update whenever the observation is not eligible for baseline learning; otherwise the detector gradually learns an ongoing abnormal episode as the new normal. 

Method	Best V1 use	Strengths	Major weakness	Compute / memory profile	Recommendation
Median + MAD / rolling quantiles	Personal center/spread, point deviations, routine ranges	Robust, interpretable, easy to audit; no training labels. MAD is explicitly a robust scale estimator. 
Does not inherently model temporal persistence or complex correlations; MAD assumes a center-based notion of spread and can be inefficient for some distributions. 
Exact rolling implementation needs a finite window/history; on backend, tens of features × thousands of observations is trivial.	Build now. Core V1 baseline.
EWMA	Gradual/sustained shifts in movement, respiration, sleep/rest-like metrics	Recursive, O(d) state, highly interpretable; NIST notes sensitivity to small/gradual mean shifts. 
Can adapt into an anomaly if updates are not gated; correlated/nonstationary behavior complicates classical control limits.	O(d) per observation and O(d) memory.	Build now, but baseline updates must be frozen during concerning/ambiguous states.
CUSUM	Persistent directional changes	Sensitive to small systematic shifts like EWMA. 
Extra tuning and overlapping role with EWMA for MVP.	O(d) online.	Optional after MVP unless a specific metric benefits.
Change-point / PELT	Detecting longer-lived regime changes in routine/baseline	Exact segmentation under its cost formulation; PELT can have linear computational cost under the conditions in the original paper. 
Better suited to accumulated sequences than immediate safety alerts; penalty/cost choice materially affects results.	Backend batch process; practical cost can be near-linear under assumptions, with sequence memory.	Shadow/offline V1, e.g. daily routine-shift analysis.
Isolation Forest	Multivariate unknown_anomaly after clean baseline history accumulates	Unsupervised, sub-sampling, low memory/compute relative to many alternatives; original paper reports linear-time/low-memory behavior. 
Ignores sequence structure unless temporal features are engineered; “anomaly” has no inherent meaning/cause.	With a few dozen features, 100-ish trees and small subsamples, comfortably backend-scale; exact size implementation-dependent.	Shadow mode during MVP; promote only after event-level validation.
One-class SVM / LOF	Experimental multivariate novelty	Can model nonlinear/local boundaries	Sensitive to scaling/hyperparameters; training/inference burden grows with retained examples; harder to explain operationally.	Higher dependence on training-set size than robust statistics.	Postpone.
Autoencoder / sequence autoencoder	Nonlinear multivariate/temporal reconstruction	Can learn complex structure without anomaly labels	Requires representative “normal” data, architecture tuning and much stronger validation; normal-trained AEs may still reconstruct anomalies well, a failure explicitly motivating MemAE. 
Training may require GPU and large datasets; inference can be smaller but audit/data burden dominates.	Do not build for V1.
Supervised multimodal deep model	Narrow event classification once you own a substantial matched dataset	Potentially powerful when domain-matched	Public benchmark accuracy can collapse under new people/rooms/hardware; difficult missing-modality behavior and debugging. CSI datasets explicitly expose domain variability. 
Highest training/data complexity.	Postpone.

A concrete personalization schedule can use two calibration levels rather than pretending a resident is “fully calibrated” after a timer expires. As an engineering starting point, allow basic robust baselines after roughly one day of clean observations but keep routine/time-of-day anomaly confidence capped until approximately a week of usable coverage exists. What matters is coverage of contexts, not wall-clock age: seven calendar days with the resident mostly away is weaker than three dense days across sleep, morning, afternoon and evening. These durations are V1 configuration hypotheses and must be validated from field data, not presented as evidence-backed thresholds.

Baseline updates should be blocked when: resident away; possible multiple people; sensor configuration changed; modality quality is poor; a concerning candidate episode is active; an unresolved unknown anomaly exists; or a modality has entered recalibration. This is consistent with your project brief and prevents classic adaptive-detector “baseline poisoning.” 

Turning scores into persistent episodes
Anomaly scores are not events. A production event manager should convert noisy overlapping windows into one stateful episode:

quality OK AND score > T_on

evidence disappears before persistence

persistence / corroboration satisfied

new windows update evidence

score < T_off

evidence returns

quiet period satisfied

materially new recurrence

Normal

Candidate

ActiveEpisode

Resolving

Resolved



Show code
Use two thresholds: (T_\text{on} > T_\text{off}). That hysteresis stops events from flickering when a score oscillates around a boundary. Add event-specific persistence such as “(k) of the last (n) windows” or a minimum dwell duration. Classical control-chart design has the same fundamental problem—balancing fast detection against false positives—although your application should tune thresholds against event-level false alerts per monitored day, not textbook process-control limits. 

For a fall-like event, persistence does not mean waiting many minutes. A useful engineering state machine is: rapid transition detected → require coherent spatial/kinematic evidence → inspect a short post-transition interval for floor-level posture or reduced motion → open one episode. For a routine-change anomaly, persistence may be tens of minutes or hours. For respiration, windows should be much longer than movement windows because rate/spectral estimates require multiple physiological cycles. These are event-dependent design constraints rather than universal thresholds.

To reduce alert spam, every episode needs a deduplication key and lifecycle. Windows for the same event family, resident/room and continuous physical condition should update one episode instead of creating new alerts. During an active episode, send another notification only when the condition resolves and recurs, severity materially escalates, or policy explicitly requires timed escalation. A continuously low-mobility resident should therefore create one inactivity episode, not 120 alerts because 120 overlapping windows crossed the threshold.

Heart-rate feasibility and confidence policy
Contactless HR is where this project is most likely to fool itself.

The physics are real. Minute chest/body-surface displacement caused by cardiac activity modulates radar phase, and early 60-GHz systems such as mmVital reported strong controlled-condition results. More recent systems have continued improving range-bin selection, harmonic separation and multi-scattering-point combination. 

But the deployment problem is also real. Pi-ViMo's authors explicitly motivate their work by noting that much prior radar vital-sign research assumes a fixed location and still subject. Even after their more robust method, reported average HR error was 11.9% while stationary and 13.6% under micro random body movements. A newer harmonic-MUSIC study reports promising percentile errors, but controlled experiments showing a heartbeat component are still not equivalent to uninterrupted bedroom monitoring across posture changes, bedding, multiple people and ordinary movement. 

Therefore the V1 policy should be:

Radar respiration: production-capable only after your hardware validation, with quality gating.

Radar HR: experimental observation, logged and benchmarked, but excluded from caregiver alert logic.

ESP32-S3 CSI HR: research-only. Espressif's official material supports environmental sensing and subtle activity such as breathing, but does not provide production validation for heart-rate measurement. 

The radar HR processor should not continuously emit a forced BPM value. It should emit:

{estimate_bpm, signal_quality, motion_contamination, target_stability, spectral_peak_ratio, harmonic_ambiguity, window_duration, coverage_state}

and often the correct estimate_bpm should be null.

An engineering starting gate could require all of the following: exactly one stable radar target; track remains within the validated distance/angle envelope; no meaningful gross movement; adequate phase SNR/coherence; a continuous 20–30-second analysis window; agreement between independent spectral/template estimates; and no obvious respiration-harmonic ambiguity. The duration and quality boundaries are starting hypotheses, not validated clinical criteria.

The most important HR metric is therefore not just MAE. Track:

[ \text{coverage}= \frac{\text{time the system chooses to report HR}} {\text{eligible monitored time}} ]

alongside median/mean absolute error, 90th/95th percentile error, failures by posture, failures by range, and failures during motion. A model that reports within ±3 bpm for 20% of carefully selected still periods is fundamentally different from one that achieves the same error over 90% of real monitored time.

Do not create “abnormal heart rate” caregiver events from an unvalidated radar estimate. That would convert an experimental RF inference into a medical-sounding assertion. A safer eventual architecture is:

objective output: “radar-derived cardiac periodicity changed substantially from this resident's validated resting baseline; measurement confidence moderate”

rather than:

“resident has tachycardia.”

Even that first statement belongs after a ground-truth study demonstrates acceptable error and coverage in your actual hardware/room envelope.

Public datasets, repositories, and validation strategy
Public data should be used to bootstrap processors, reproduce literature methods, design schemas and test training code. It should not be used to certify product performance because hardware, room geometry, placement, resident population and event prevalence differ.

Resource	Modalities / scope	Why useful for this V1	Important limitation	Access / licensing note
eHomeSeniors	MLX90640 32×24 thermal plus Omron thermal; public fall dataset. MLX data are ~16 fps and include 768 temperatures plus raw fields. 
Best direct bootstrap for MLX90640 fall geometry, preprocessing, centroid trajectories and file ingestion.	Staged falls, one-person limitation, data collected in a relatively sparse 6×5-m experimental room; not radar/CSI synchronized. 
Public supplementary dataset. Verify exact reuse terms for your intended commercial workflow before incorporating data artifacts.
EAVISE MLDetection	MLX90640 32×24 person detection, ceiling-mounted at 90°/45°, offices/labs/residential rooms. 
Excellent for occupancy/blob/person detector experimentation and placement comparison.	Person detection, not a fall/physiology dataset.	Direct university-hosted download; ~200-MB dataset listed by KU Leuven. 
Taramasco et al. multimodal fall dataset	Ten participants simulating ten fall types; FIR thermal, 60–64-GHz radar, 8×8 LiDAR and phone accelerometer. 
Most conceptually aligned public resource for testing thermal + 60-GHz radar fusion and temporal alignment.	Staged falls and small participant count; sensors/placement are not guaranteed to match your stack; no CSI.	Published as a 2025 PeerJ dataset paper. Confirm underlying data license/commercial terms directly before product use.
MM-Fi	>320k synchronized frames, 40 subjects, four environments, mmWave, Wi-Fi CSI plus other modalities and 27 activities. 
Strong bootstrap for multimodal data loaders, synchronized radar/CSI representation, cross-environment tests and action features.	Not your exact radar/ESP32 CSI hardware; young-subject action dataset, not fall/vital-sign or long-duration anomaly monitoring.	Official NTU-AIoT project/toolbox provides dataset access; verify dataset-specific reuse terms. 
Widar3.0	Large Wi-Fi CSI gesture/domain dataset; filenames explicitly encode room, position, orientation and receiver. 
Excellent for CSI preprocessing, Doppler/DFS ideas and domain-shift experiments.	Commodity CSI acquisition differs from ESP32-S3; gesture recognition is not room-monitoring anomaly detection.	Official Tsinghua project provides download/instructions. 
CI4R-MULTI3	TI IWR1443-class radar activity data across multiple activities. 
Useful for radar HAR/point-cloud tooling and reproducible baselines.	77-GHz hardware and activity protocol differ from the assumed 60-GHz V1.	University research resource; verify terms.

The best implementation repositories/resources are similarly asymmetric. Espressif esp-csi should be your starting point for ESP32-S3 capture because it is the vendor's official project, supports the ESP32-S3 family, includes receive/router/device examples and is Apache-2.0 licensed. 
 Melexis's official MLX90640 software/driver material, linked directly from the current datasheet page, should be the calibration/temperature-conversion reference rather than a random Arduino implementation. 
 For mmWave, use TI's SDK/Radar Toolbox/reference labs for board configuration, point clouds and vital-sign experiments rather than implementing the radar stack from scratch. TI's hardware itself provides DSP and HWA for the core signal-processing chain. 

The public MM-Fi author toolbox is worth using to understand synchronized multimodal organization and cross-domain evaluation, while Widar3.0 provides processed DFS/BVP resources alongside CSI and explicitly documents room/location/orientation domains. Those are useful algorithmic references, not drop-in models for ESP32-S3. 

Your own dataset matters more than the public ones
The first real hardware campaign should not be a massive ML data collection. It should be designed to falsify the sensor assumptions:

Experiment	Variables to sweep	Ground truth / output	Decision it should unlock
Occupancy and away	Distance, room position, sitting/lying/standing, doorway, blankets, fans, heating, one vs two people	Manual/video ground truth retained only for R&D if privacy allows	Which modalities can independently establish presence; coverage/FOV limitations.
Falls and confounders	Forward/back/lateral falls, controlled descents, kneeling, picking up objects, sitting quickly, lying on floor, dropped bedding	Synchronized external ground truth	Transparent fall feature thresholds and false-positive confounders.
Inactivity	Quiet reading, sleeping, sitting still, away room, sensor obstruction	Presence ground truth	Distinguish “present but still” from away/failure.
Radar respiration/HR	Supine/prone/side/seated, different distances/angles, blankets, small movements	Reference respiration belt + validated ECG/PPG/pulse-oximeter device	Reportable coverage and error envelope.
CSI stability	Furniture moved, door open/closed, fan, router reboot/channel change, people crossing adjacent space, different antenna placements	Environment log	Which CSI features survive ordinary room changes; recalibration triggers.
Missing/conflicting modalities	Unplug one sensor, stale UART, dropped packets, frozen frames, induced channel switch	Test harness truth	Monitoring-degraded policy, TTLs, event suppression and recovery.

Evaluation must be performed at the session/person/room level, not by randomly distributing overlapping windows from the same recording across train and test. For CSI especially, room/location/orientation are explicit domains in established datasets, so a random-window result can substantially overstate real deployment generalization. 

The MVP scorecard should emphasize operational metrics:

Fall-like events: event sensitivity/recall, event precision, false events per monitored day, detection latency.

Inactivity/routine anomalies: events per day/week, episode duration error, alert deduplication rate.

Sensor reliability: percentage of time full, limited, and unavailable; sensor-drop recovery latency; false anomalies caused by sensor faults.

Personalization: clean hours contributing to baseline, fraction of candidate events excluded from baseline updates, stability after room/device changes.

Vitals: MAE and high-percentile error plus reporting coverage, stratified by posture, distance, movement and room.

Window-level “99% accuracy” should be secondary. In a continuous-monitoring system, even a tiny false-positive probability per short window can generate an intolerable number of daily episodes if the event manager is poor.

Simplest defensible V1 and three-month MVP
The architecture below deliberately keeps replaceable boundaries between measurement, quality, anomaly evidence and event policy. That is the design most likely to survive hardware changes and later ML upgrades.

60-GHz mmWave radar

Radar edge DSP
range/Doppler/angle
point cloud + tracks
micro-motion phase

MLX90640
32×24 thermal

Thermal processor
temperature frame
blobs + geometry
motion features

ESP32-S3 CSI

Fast CSI capture
queue/ring buffer
metadata + raw vectors

CSI processor
filtering
amplitude/phase features
STFT / motion bands

Per-modality quality
availability / usable_for

Time alignment +
    normalized observation store

Event-specific scorers
presence
fall-like
inactivity
repeated motion
respiration
unknown anomaly

Personal baseline
median/MAD
bounded EWMA

Hysteresis +
persistence +
corroboration

Episode manager
merge / cooldown
resolve / recur
escalation

Caregiver/API event

Audit/debug store
    bounded raw/event snippets
    config + algorithm versions

Monitoring state
full / limited / unavailable



Show code
Build now
The sensor observation contract is first. All real hardware and the simulator must produce the same conceptual fields. Do not let the backend care whether a radar point cloud came from a simulator or an IWR6843.

For radar, build point-cloud/track ingestion, movement/vertical-change features, time-since-motion, target-count logic and the separate micro-motion channel. Use TI's onboard processing rather than starting with raw ADC production transport. 

For thermal, preserve 32×24 temperature frames, build adaptive background subtraction, body/blob extraction, centroid/bounding geometry, vertical extent, floor-proximity and temporal motion. At this resolution a full frame is cheap, and both eHomeSeniors and EAVISE demonstrate that 32×24 data preserve useful person/fall geometry. 

For CSI, build reliable packet acquisition before sophisticated sensing: controlled packet source, sequence/timing metadata, queueing, raw vector logging, channel/config-change detection and basic amplitude/differential features. Espressif's own guidance to keep callbacks short should drive the firmware architecture. 

Build an explicit quality engine and the states full_monitoring, limited_monitoring, unavailable, possible_multi_person, calibrating and recalibrating. This is more important than squeezing another few points of activity-classification accuracy because every later algorithm depends on deciding which measurements are trustworthy.

Build median/MAD + bounded EWMA personalization, initially for a compact feature set such as occupancy probability, movement energy, location/centroid zones, inactivity duration, radar respiration rate/quality and coarse activity level. Keep time-of-day context simple at first; expand only when enough resident history exists. The statistical basis is mature and computationally trivial compared with learned temporal models. 

Build deterministic event state machines for presence/away, fall-like transitions, inactivity, elevated/repetitive movement, respiration deviation, unknown anomaly and monitoring degradation. Every candidate event should save objective evidence, quality, baseline values, configuration version and exactly which rule transitioned the episode state.

Finally, run Isolation Forest in shadow mode only on normalized backend features. Log where it disagrees with the transparent system. That gives you real evidence about whether nonlinear multivariate anomaly detection adds product value without putting unvalidated output in front of caregivers. Its original design is specifically attractive for low-memory, sub-sampled anomaly detection, which makes this experiment inexpensive. 

Postpone
Do not build an end-to-end multimodal transformer/autoencoder, resident-identification model, CSI pose estimator, deep multimodal fall classifier, learned attention-based fusion, or caregiver-facing HR alert system in the MVP. Public multimodal datasets such as MM-Fi are valuable, but their modalities, people and environments do not make a model automatically transferable to your rooms and hardware. 

Do not solve multi-person identity. Detecting that multiple people may be present is enough for V1; freeze personalized inference rather than guessing which RF/thermal signature belongs to the resident. This is consistent with the one-resident/no-identity product constraint in your brief. 

Do not invest heavily in exact heart-rate estimation until the basic radar respiration and motion-quality pipeline has been benchmarked. The published gap between stationary and moving HR performance is already a warning that sophisticated HR processing can consume substantial engineering effort while still having low real-world coverage. 

Do not build a “general AI health interpretation” layer into the safety path. The system's defensible output is what changed, for how long, which sensors support it, and how trustworthy those measurements were. Cause and diagnosis are separate questions.

Engineering decision table
Component	V1 decision	Why	Replacement boundary / later upgrade
Radar telemetry	Point cloud/tracks + selected micro-motion phase; debug ADC snippets only	Uses IWR6843 DSP/HWA and avoids huge raw transport while preserving vital-sign research evidence. 
Replace radar processor without changing normalized observations.
Thermal telemetry	Retain full 32×24 temperatures at 8–16 Hz	Tiny bandwidth and materially useful geometry; MLX90640 supports up to 64 Hz but 16-Hz implementations are already practical. 
Later edge-compress/features-only if privacy/storage requires it.
CSI telemetry	Raw complex CSI + metadata at controlled packet cadence	Preserves subcarrier information; official ESP32 support exposes complex channel data and metadata. 
Replace backend features/model independently.
Sensor quality	Vector + usable_for objectives	Same stream can be valid for motion and invalid for HR.	Later learn quality calibration, but keep explicit dimensions.
Fusion	Event-specific late fusion + deterministic gates	Modalities measure different physics; easier missing-data behavior and auditing.	Learned probabilistic fusion can later replace individual scorers.
Baseline	Median/MAD + bounded EWMA	Robust, transparent, cheap and appropriate to small/sustained shifts. 
Add contextual Bayesian/change-point models later.
Unknown anomaly	Robust multivariate deviation; Isolation Forest shadow	Transparent production path with cheap nonlinear experiment. 
Promote iForest or later one-class model after real-room evidence.
Falls	Transition + geometry + post-event state machine	Uses physically meaningful independent evidence; avoids peak-only alerts. Thermal/radar literature supports geometry/trajectory evidence. 
Add learned fall scorer as one evidence input, not as whole event workflow.
Respiration	Radar primary; CSI corroboration	Radar micro-motion literature is much stronger; official CSI supports subtle sensing but not equivalent validation. 
Improve radar phase/range-bin processing later.
Heart rate	Experimental radar output; no HR alert	Controlled studies still show meaningful error and motion sensitivity. 
Promote only after ground-truth validation of accuracy and coverage.
Event management	Hysteresis, persistence, merge, cooldown, recurrence	Window anomaly ≠ caregiver event; operational false alerts matter.	Tune from pilot event data without replacing sensor models.
Deep multimodal model	Not V1	Large validation/domain-shift burden and poor explainability under missing modalities. CSI domain variation is well documented. 
Consider only after matched multi-room dataset exists.

Three-month MVP timeline
A practical MVP beginning immediately after the current August 2026 planning point looks like this:

Sep 06
Sep 13
Sep 20
Sep 27
Oct 04
Oct 11
Oct 18
Oct 25
Nov 01
Nov 08
Nov 15
Nov 22
Nov 29
Observation schema + replay simulator
Radar / thermal / CSI capture pipelines
Clock, sequence and raw-debug logging
Radar tracks + motion features
Thermal blob / geometry processor
CSI cleaning + motion features
Quality / usable-for engine
Median-MAD + EWMA personalization
Presence / inactivity / fall state machines
Event fusion + hysteresis / episode manager
Isolation Forest shadow experiment
Structured room / fall / confounder recordings
Respiration + experimental HR validation
Missing-sensor / conflict / recovery testing
Event-level threshold tuning
Continuous pilot and false-alert audit
V1 algorithm/config freeze
Contracts and acquisition
Sensor intelligence
Baselines and events
Validation
MVP freeze
Three-month contactless monitoring MVP


Show code
The first month exit criterion should not be “AI recognizes activities.” It should be: all three modalities produce timestamped replayable observations; sensor failures are distinguishable from resident changes; and simulator data can be swapped for hardware without changing downstream interfaces.

The second month exit criterion should be: personal baselines update only from eligible data; each event family has objective evidence and deterministic persistence logic; missing one modality degrades confidence rather than causing crashes or fabricated values; and repeated overlapping windows merge into episodes.

The third month exit criterion should be: you can report event-level false alerts/day, miss rate and latency from structured recordings; you know exactly which postures/ranges permit radar respiration and HR estimation; you have deliberately tested furniture/network/sensor changes; and every emitted event is reproducible from saved algorithm/config versions and objective evidence.

The simplest defensible production logic at the end of those three months is therefore:

Acquire rich but bounded modality-specific observations. Reject or downgrade bad measurements. Establish whether the resident is plausibly present and whether the room is single-person. Compare trustworthy objective features against a robust personal baseline. Create event-specific evidence using radar, thermal and CSI only where each modality is physically relevant. Require persistence or corroboration before opening an episode. Merge repeated windows into that episode. Report the observed change, evidence and confidence—never a fabricated cause. Keep HR experimental.

That architecture is less glamorous than an end-to-end multimodal neural network. It is also much more likely to survive first contact with an actual bedroom.

