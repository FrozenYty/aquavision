*Internship and Training Centre*

*Software Engineering Comprehensive Training*

# Underwater Species Detection and Monitoring for Marine Ranching Based on an Improved YOLOv8

*Software Project Requirements Specification*

| Item | Content |
|---|---|
| Document title | Underwater Species Detection and Monitoring for Marine Ranching Based on an Improved YOLOv8 — Software Project Requirements Specification |
| Document number | SRS-PRJ14-V1.13-2026 |
| Project number | PRJ-14 |
| Document version | V1.13 |
| Phase | Phase 1: requirements analysis |
| Prepared by | Training Group 14 |
| Project lead | Yao Tianyu (group lead); supervisor: Wu Jianguang |
| Technology stack | Frontend HTML5/CSS3/JavaScript + Bootstrap 5 + hand-rolled SVG charts · Backend Python 3.11 (FastAPI + SQLAlchemy), SQLite locally and PostgreSQL 14 in deployment · Algorithm PyTorch 2.1 + Ultralytics YOLOv8 + OpenCV · Capture USB camera (1080P, fixed-focus adjustable, manual exposure, driver-free UVC) + OpenCV capture (the microcontroller is an optional enhancement, not part of the main stack) |
| Project duration | 8 weeks |
| Date | 2026-11-03 |
| Classification | Internal (teaching use) |

> This document is the requirements specification for the training project "Underwater Species Detection and Monitoring for Marine Ranching Based on an Improved YOLOv8". It is the single requirements input for every later phase: prototyping, database design, high-level design, algorithm development, coding and testing.

## 1 Introduction

### 1.1 Purpose

This document describes the business goals, user roles, functional requirements, data requirements, interface requirements, algorithm and model requirements, and non-functional requirements of the software project "Underwater Species Detection and Monitoring for Marine Ranching Based on an Improved YOLOv8" (hereafter "the system" or "AquaVision"). It also states the acceptance criteria and the implementation milestones. Its readers are the project supervisor, the development team, the algorithm and test staff, and the acceptance reviewers.

Its specific uses are:

- the formal deliverable of the requirements phase, fixing what the system does and what the algorithm detects, and settling module boundaries and priority so that scope cannot drift during development;
- the direct input to prototyping, database design, high-level design and algorithm design, so that later designs map back to requirements item by item;
- the acceptance basis for training, coding and testing, giving explicit pass criteria for functional, accuracy, performance and acceptance tests;
- the formal material for reviews and the final defence, supporting the argument that requirements are traceable.

### 1.2 Background

Resource surveys, stock assessment and predator monitoring in marine ranching and coastal cages have long depended on divers reading the seabed visually or on people replaying underwater video. A routine inspection produces hours of 1080P footage, and manual reading takes several times the recording length. Results vary with experience, fatigue and subjective judgement: a trial count over three clips by this group showed up to 20 % disagreement on the same species. Historical footage sits in loose files that cannot be searched and cannot form a comparable time series, so trend analysis, predator outbreak warning and restocking evaluation lack objective data.

Underwater imaging also makes automatic detection hard. Water absorbs red strongly, pushing the image blue-green; suspended particles and plankton scatter light into haze; uneven lighting and artificial sources create hot spots and dark zones; benthic species — sea cucumber, sea urchin, scallop, starfish — resemble rock and seagrass and occlude one another; fish are small, dense and motion-blurred. A detector trained on a general dataset transfers poorly: it misses targets, invents them, and counts the same individual twice in one frame.

This project targets three businesses — marine ranch inspection, coastal cage monitoring and fishery resource survey — and builds a web system around YOLOv8 object detection that closes the loop from capture and ingestion through detection and counting, human review, statistics and reporting, to annotation and model iteration. The system turns underwater footage into structured species, count, position and time data, supporting density assessment, trend analysis and predator warning, and leaves interfaces for ROV live video and edge deployment.

### 1.3 Scope

#### 1.3.1 Goals

- A unified management system for underwater imagery covering capture sessions, monitoring sites, camera parameters and water conditions, with multi-dimensional search.
- Automatic detection and counting built on YOLOv8, returning class, bounding box, confidence and a de-duplicated individual count per frame.
- A quality loop from automatic detection through human review to stored results, where corrections flow back as training samples and form the channel for model iteration.
- Multi-dimensional statistics and alerting: composition, density distribution and trend by site, time and species, with rule-based anomaly and trend warnings.
- A runnable, demonstrable web system with a complete algorithm and business loop, delivered in 8 weeks, together with the process documents that show the team can practise software engineering.
- Capture straight from the camera on opening the system, with no file import of any kind.
- The improved model beats the baseline by at least 0.03 mAP@0.5 and keeps FPS at 90 % of the baseline or better.

#### 1.3.2 In scope

- Registration and sign-in, role permissions, team and account management, operation log and audit.
- Continuous capture from the local camera, metadata registration, quality scoring and retake, retention and cleanup.
- Creating detection jobs, queue scheduling, progress monitoring, cancel and retry, and re-running a job.
- Model version registration, activation and switching, inference engine and device configuration, metric recording and baseline comparison, per-class confidence thresholds.
- Browsing results, manual review and correction, filtering and batch operations, export in CSV / JSON / COCO / VOC and as annotated images or video.
- Species dictionary and field guide, hard-example library, online annotation, dataset versioning, training job management and metric visualisation.
- Site and capture-session management, quality alerts, dashboards and report export.
- System parameters, runtime monitoring, announcements, data dictionary and coding rules, backup and restore.

#### 1.3.3 Out of scope

- Control of ROV or camera attitude, track and gimbal; no underwater navigation and no engineering of a waterproof housing. Capture happens on the local machine.
- Integration with live marine-ranch production or billing systems. All data is teaching data and simulated business.
- Fishing decisions, restocking plans or disease prescriptions. Analysis and alerts are reference and technical hints only.
- Cross-day re-identification of individuals or precise growth-curve fitting. Length estimates rest on pixel calibration and are labelled as estimates.
- Native mobile apps or mini-programs; only a responsive web UI. No multi-tenant SaaS and no cross-organisation data isolation.

### 1.4 Terms and abbreviations

**Table 1-1 Terms and abbreviations**

| Term | Abbreviation | Meaning |
|---|---|---|
| Software requirements specification | SRS | This document. States functional and non-functional requirements and serves as the input and acceptance basis for design, development and testing. |
| Use case | UC | A complete description of a user interacting with the system to reach a goal: actors, preconditions, main flow, alternative flows, postconditions. |
| Functional requirement | FR | A concrete business capability the system must provide, numbered FR-<module>-<index>. |
| Non-functional requirement | NFR | A quality attribute: performance, accuracy, security, availability, maintainability. |
| Prototype | Proto | A low- or high-fidelity interface model used to validate requirements and interaction, produced after requirements analysis and before database design. |
| High-level design | HLD | The description of overall architecture, module division, interfaces between modules and data flow; the last design activity before coding. |
| Minimum viable product | MVP | The runnable version delivered within 8 weeks, covering the core business and algorithm loops. |
| YOLO | YOLO | The You Only Look Once family of single-stage detectors. This project uses Ultralytics YOLOv8 as the baseline and improves on it. |
| Mean average precision | mAP | The aggregate accuracy metric for detection. This project accepts on mAP@0.5 and mAP@0.5:0.95. |
| Intersection over union | IoU | Intersection area over union area between predicted and ground-truth box; used for positive/negative assignment and non-maximum suppression. |
| Non-maximum suppression | NMS | The post-processing step that keeps the highest-confidence box among overlapping predictions for one target. |
| Confidence threshold | Conf | The minimum class confidence for a detection to be accepted, configurable per species, balancing misses against false positives. |
| Remotely operated vehicle | ROV | A tethered submersible carrying a camera for inspection footage; the main source of imagery in production. |
| Frames per second | FPS | The throughput metric for detection on a video sequence; the numbers are in the table in 3.5.4. |
| Cross-frame de-duplication | Dedup | Merging repeated detections of one individual across consecutive frames so that it is counted once. |
| Annotation | Anno | Drawing bounding boxes and assigning classes to form training samples. This project provides online annotation and automatic pre-labelling. |
| Dataset version | DS | A frozen snapshot of a fixed sample set and split, so that training runs are reproducible. |
| Open Neural Network Exchange | ONNX | A cross-framework model format used to export the trained PyTorch model for accelerated inference and deployment. |

### 1.5 References

**Table 1-2 References**

| Number | Title | Use |
|---|---|---|
| GB/T 8567-2006 | Specification for computer software documentation | Basis for structure and drafting of this specification |
| GB/T 9385-2008 | Specification for computer software requirements specifications | Reference for requirement description, quality attributes and itemisation |
| GB/T 19001-2016 | Quality management systems — fundamentals and vocabulary | Reference for process management and quality records |
| GB/T 35273-2020 | Information security technology — personal information security specification | Reference for account data, logs and privacy compliance |
| IEEE Std 830-1998 | Recommended Practice for Software Requirements Specifications | Reference for structure and traceability |
| arXiv:1804.02767 | YOLOv3: An Incremental Improvement (Redmon & Farhadi, 2018) | Reference for the YOLO family and detection head design |
| Ultralytics Docs | Official YOLOv8 documentation and training/inference API | Direct basis for baseline choice, hyperparameters and export |
| DUO dataset | Detecting Underwater Objects, COCO-format annotations | Training and test data for the four classes; official split, 1111 test images |
| OpenCV Docs | OpenCV 4.x documentation (video I/O, enhancement, colour correction) | Reference for frame extraction, preprocessing and result drawing |
| UVC 1.5 | USB Video Class 1.5 | Basis for driver-free capture |
| OpenCV VideoCapture | OpenCV VideoCapture documentation | Basis for the capture implementation |
| SC/T 9111-2017 | Classification and construction guidelines for marine ranching (reference only) | Reference for site division, inspection vocabulary and survey definitions |

## 2 Project overview

### 2.1 Positioning and objectives

AquaVision is a web system for underwater species detection and monitoring in marine ranching, coastal cages and fishery surveys. Its main chain is capture, detection, human review, statistics and model iteration. It unifies four activities that are usually separate — underwater filming, manual reading, paper records and model experiments — onto one data model. For business users it turns footage into searchable, comparable, exportable species and count data. For algorithm staff it turns every miss and false positive into an annotation sample that can flow back into training, so accuracy improves with use. The system does not replace the professional judgement of fishery staff; it removes repetitive visual reading, leaving specialists to handle what the machine is unsure about, and turns each of their judgements into input for the model.

The overall objectives are:

- Single-frame end-to-end detection within 1.5 s, continuous capture at no less than 1 frame/s, and every result traceable to the model version that produced it.
- On the test set, mAP@0.5 of at least 0.75 for the core species, and a count deviation from manual reading of no more than 15 %.
- Review results flow back as training samples with one click, and a full iteration — annotate, train, evaluate, deploy — completes within one working day.
- Any result traces back to the image file, model version, detection parameters and operator, so conclusions are reproducible and auditable.

### 2.2 User roles

**Table 2-1 User roles**

| Role | Description | Technical and permission profile | Core need |
|---|---|---|---|
| Collector | Front-line inspector at the ranch or cage, responsible for filming and quality control. | Signs in and uses the system; controls capture, creates and views their own detection jobs and results; cannot change models or system parameters. | Get results from the current inspection quickly, and know what is at each site and how much of it. |
| Analyst | Specialist in resource assessment and data analysis; reviews results, analyses spatial and temporal distribution, produces inspection reports. | Views all jobs and results; may review, correct, export and generate reports; maintains the species dictionary and sample library. | Results that are trustworthy and correctable, and charts and reports ready to present. |
| Algorithm engineer | Handles annotation, training, evaluation and deployment, improving accuracy and speed. | Full access to the annotation bench, dataset management, training jobs and model management; registers and activates model versions. | Hard examples collected automatically, reproducible experiments, and comparable metrics before and after deployment. |
| Administrator | Owns accounts and permissions, sites and equipment records, alert rules, system parameters, monitoring and backup. | All management permissions plus audit log access; disables accounts, configures parameters, watches runtime and exports logs. | A system that stays up, clear permission boundaries, controlled storage and compute, and traceable problems. |

### 2.3 Typical scenarios

**Scenario 1 — capture and immediate detection.** The inspector puts four kinds of target into the observation tank; the camera is fixed against the outer wall with exposure locked. They press "start capture"; the system grabs one frame per second, overlays boxes on the main view, and within 3 s shows "sea cucumber 3, sea urchin 2, scallop 4, starfish 1" on the right together with the end-to-end time for that frame.

**Scenario 2 — quality rejection and retake.** A frosted sheet is slid in to cloud the water and the frame goes grey. The system scores it 48, marks it "needs retake" and keeps it out of the detection queue. The sheet is removed and the next frame scores 86, enters detection automatically, and the count updates.

**Scenario 3 — review and sample return.** In the review bench the analyst finds a sea cucumber classified as rock, draws one more box and changes the class. After submitting, the count goes from 10 to 11, the frame enters the hard-example pool, the dataset version moves from DS-V2 to DS-V3, and all three changes are visible on the page.

**Scenario 4 — experiment and deployment.** The algorithm engineer trains an improved model on DS-V3. The experiment page shows mAP@0.5 rising from 0.76 to 0.83 against the baseline and FPS falling from 42 to 39. The version is registered and activated; new jobs use it automatically and the job detail records the version.

**Scenario 5 — statistics and report.** The analyst generates a monthly inspection report: species composition, site distribution, quality rejection rate and alert summary, with the model version and statistical basis in the footer. The report is delivered as Markdown and earlier versions stay retrievable.

### 2.4 Architecture and data flow

The system has three layers — capture, service and presentation — which exchange data only through in-process calls and local files. It depends on no external device and no network stream. The direct purpose of this design is to satisfy the constraint that imagery must come from a camera: there is no entry point that takes a picture from local disk into detection, so everything in the detection queue can only have come from a live grab on this machine.

#### 2.4.1 Layer responsibilities

- **Capture layer**: USB camera, trigger board and turbidity sensor. Grabs raw frames, locks exposure and white balance, reports water parameters, and performs no inference.
- **Service layer**: capture service, detection service, job queue, file storage and PostgreSQL. Scores quality, stores frames, schedules detection, persists results and aggregates statistics.
- **Presentation layer**: 13 browser pages. Capture control, result review, statistics and reports, model experiments.

#### 2.4.2 Seven steps for one frame

- ① **Open the camera**: on start-up, enumerate local video devices and take the first available one by default.
- ② **Lock exposure**: read the current exposure, lock it, and fix white balance and gain. If locking fails, refuse to start capture.
- ③ **Grab and read sensors**: take frames at the configured rate (1 frame/s by default), discard the first, read turbidity and report it with the frame.
- ④ **Score quality**: weighted score over sharpness, brightness and colour cast; below 60 means retake.
- ⑤ **Register**: store on disk as site/date/index, write the image row and generate the resource code.
- ⑥ **Queue for detection**: passing frames enter the queue; failing frames are stored but not queued, and a retake is prompted.
- ⑦ **Present**: results go to the target table, pages aggregate by job, and the end-to-end time is recorded with them.

#### 2.4.3 Capture interface conventions

- **Device**: local UVC camera, 1080P, MJPEG or YUYV, device index configurable.
- **Exposure**: manual, shutter and gain fixed; once locked, mean brightness between frames varies by no more than 10 %.
- **Frame rate**: 1 frame/s by default, adjustable from 0.2 to 5.
- **Timestamp**: the server's receive time to the millisecond, stored alongside UTC.
- **Idempotence**: the frame index is unique within a capture session; grabbing twice does not create a second record.
- **Environment**: turbidity is reported per frame as a relative value (0 clear, 100 most turbid), sampled every 5 s; with no sensor the field stays empty and is excluded from statistics.
- **Failure**: if the camera is unavailable the capture is marked failed with a prompt to check the device, and no empty record is written.

### 2.5 Environment and constraints

#### 2.5.1 Technical environment

**Table 2-2 Software and hardware environment**

| Element | Choice and requirement |
|---|---|
| Frontend | HTML5 + CSS3 + JavaScript (ES6), Bootstrap 5 grid and forms, hand-rolled SVG charts (bar, line, pie, heat map), Canvas annotation surface, Fetch against the REST API, polling for job progress plus result-page refresh, high-fidelity HTML prototype in the prototype phase |
| Backend | Python 3.11 + FastAPI (REST) + Pydantic validation + SQLAlchemy 2.1 ORM + JWT authentication. Asynchronous jobs run in a fixed thread pool inside the same process — no Celery, no Redis (ADR 03) |
| Algorithm | PyTorch 2.1 + Ultralytics YOLOv8 (baseline and improved) + OpenCV 4.x (frame extraction, preprocessing, drawing) + NumPy + Albumentations (augmentation) + ONNX / ONNXRuntime (accelerated inference) |
| Database | PostgreSQL 14 (UTF-8), five table groups by domain — user, image, detection, model, alert — with indexes and partitioning for large tables |
| File storage | Local filesystem for originals, extracted frames, thumbnails and result images; paths configured centrally and cleaned automatically by retention days |
| Tooling | Git, GitHub private repository, Postman for API debugging, VS Code, PyCharm, DBeaver, Label Studio for cross-checking annotations |
| Deployment | Development on Windows 10 / Python 3.11; a single Linux server (NVIDIA GPU, at least 8 GB VRAM, inference peak at most 6 GB; training on rented GPUs or a group laptop with a discrete GPU, demonstration on the same machine), Nginx reverse proxy + Uvicorn + PostgreSQL 14 |
| Browser | The last two major versions of Chrome or Edge, 1366×768 and above, usable down to 375 px width |

**Table 2-3 Capture and demonstration equipment**

| # | Item | Specification | Qty | Purpose |
|---|---|---|---|---|
| 1 | USB camera | 1080P, adjustable focus, manual exposure, driver-free UVC | 1 | Image capture |
| 2 | Fill light | Existing LED study lamp, 10 W, 4000 K, Ra90, no visible flicker, USB-powered | 1 | 45° fill from above; a DC supply carries no mains ripple and the honeycomb lens spreads the light evenly |
| 3 | Controller board | ESP32-S3, USB serial | 1 | Accepts the trigger, reads the turbidity sensor, drives the status display and the status LEDs, reports over USB serial |
| 4 | Turbidity sensor | ME2100A-IIC, I2C digital, reflective | 1 | Reads water turbidity, mounted against the outer wall |
| 5 | Trigger button | Tactile switch | 1 | Triggers one capture by hand |
| 6 | Demonstration tank | Ultra-clear glass tank 300×170×200 mm, 5 mm walls | 1 | Simulates an underwater scene; glass has no stress birefringence, which cross-polarisation needs |
| 7 | Polarising sheet | Linear polariser 200×200 mm, cut into a lamp piece and a lens piece | 1 | Cross-polarisation removes reflections from the wall and the water |
| 8 | Targets and scenery | Four to six real seafood items, dark stones and weed collected on site | 1 set | Objects to detect and distractors |
| 9 | Status display | 0.96" OLED, 128×64 monochrome, I2C, address 0x3C | 1 | Shows link state, turbidity, quality score and verdict; no PC needed on site |
| 10 | Status LEDs | One green and one yellow LED, 330 Ω series resistor | 2 | Green = stored, yellow = retake; flashes 300 ms in step with the screen |

#### 2.5.2 Development and operation constraints

- A fixed 8-week cycle; the requirements baseline freezes at the week-11 review, and later changes must record their impact and update the traceability matrix.
- Four people, several roles each, covering requirements, prototyping, database, algorithm, backend, frontend and testing; weeks 14-15 are the only coding window.
- The backend is limited to Python 3.11 + FastAPI, the database to PostgreSQL 14, the algorithm to PyTorch + Ultralytics YOLO. The frontend uses no framework and no build tool, and the stack mixes in no other language. The schema script must run on a clean instance in one pass and pass constraint checks.
- All interfaces are in Chinese, in a deep-sea blue and teal palette; medical blue-and-white styling is not allowed.
- Training and test data come from public underwater datasets and teaching footage, and pages must state the data source. Classified waters and real fishery locations must not be used.

### 2.6 Assumptions and dependencies

- The system runs on a single server with a GPU and no more than 10 concurrent detection jobs; load targets assume a small intranet.
- Capture uses the local USB camera and depends on no network or external device; the demonstration is filmed through an ultra-clear glass tank.
- Turbidity is reported automatically by the capture-end sensor as a 0-100 relative value every 5 s; with no sensor the field stays empty and is excluded from statistics rather than estimated.
- The public DUO dataset (four classes — sea cucumber, sea urchin, scallop, starfish — over seven thousand images with an official split) is available for teaching; additional footage is shot by the group in the tank. The training set is at least 3000 images and the test set at least 500, split by near-duplicate frame groups so that no group spans both sides.
- The supervisor holds a fixed weekly review and Q&A session, and allocates administrator accounts.

## 3 Functional requirements

### 3.1 Functional structure

The system is divided into eight top-level modules along the business chain. Unlike the usual "layered by technology" split, these boundaries follow the flow from one capture to one report, and each module maps to a definite set of screens and a group of tables.

**M1 User and permission management**

Position: sign-in, roles, account maintenance and audit; the entry point and security base of the system.

- FR-M1-01 Sign-in and session — phone or email sign-in, CAPTCHA, lockout after failures, token issue (8 h, no refresh).
- FR-M1-02 Roles and permissions — boundaries between collector, analyst, algorithm engineer and administrator, enforced on the server.
- FR-M1-03 Account management and reset — administrators create, disable and restore accounts, and reset passwords.
- FR-M1-04 Operation log and audit — records sign-in, review, activation, parameter changes and other key actions for later tracing.

**M2 Capture and quality control**

Position: grabs frames from the local camera, scores quality, stores and cleans; the data entry for detection.

- FR-M2-01 Single-frame capture and registration — accepts a frame, records device, site, timestamp and exposure, generates a resource code.
- FR-M2-02 Scheduled and continuous capture — triggers capture on a schedule and forms batches automatically.
- FR-M2-03 Quality scoring and retake — scores sharpness, brightness and colour cast; low scores are rejected with a retake prompt.
- FR-M2-04 Batch and image search — searches batches and frames by site, time and session.
- FR-M2-05 Retention and cleanup — removes intermediate files after the retention period and produces a reviewable cleanup list.

**M3 Detection**

Position: runs the improved YOLOv8 on captured frames and outputs class, position, confidence and count.

- FR-M3-01 Immediate detection — detects a single frame and returns results and an overlay image end to end.
- FR-M3-02 Batch detection and queue — queues a batch or a frame list, with progress, cancel and retry.
- FR-M3-03 Detection parameters — confidence, IoU, per-image limit and class filter, frozen with the job.
- FR-M3-04 Result browsing and counting — overlay image and target list linked, with per-class counts.
- FR-M3-05 Export — CSV, JSON and annotated images, coordinates normalised.

**M4 Review and feedback**

Position: human correction of automatic results with a full trail, turned into training samples to form the iteration channel.

- FR-M4-01 Review bench — add, delete and edit boxes and classes on the result image, then submit a conclusion.
- FR-M4-02 Review trail and versions — every review creates a version, with diff and rollback.
- FR-M4-03 Hard-example set — collects low-confidence, corrected and cross-model-disagreement samples automatically.
- FR-M4-04 Dataset export — exports a YOLO-format dataset for a sample range and split ratio, recording a snapshot.

**M5 Statistics and reports**

Position: turns results into composition, distribution and trend, and produces a deliverable inspection report.

- FR-M5-01 Species composition — count, share and mean confidence by class, with switchable basis.
- FR-M5-02 Site and time distribution — density heat map and ranking by site, drillable.
- FR-M5-03 Trend and comparison — rate of change and significant swings by day, week and month.
- FR-M5-04 Inspection report — assembles a downloadable report from a template.

**M6 Models and experiments**

Position: registers model versions and training runs, manages activation and rollback, maintains the species dictionary and per-class thresholds.

- FR-M6-01 Version registration — version name, weights, dataset and metrics.
- FR-M6-02 Activation and rollback — single-line model switching with a change record.
- FR-M6-03 Experiments and metric comparison — baseline and improved runs in one table, with ablation view.
- FR-M6-04 Species dictionary and per-class thresholds — class code, category and default confidence threshold.

**M7 System configuration**

Position: externalised parameters so the system stays runnable and maintainable.

- FR-M7-01 System parameters — retention days, concurrency limit, default thresholds and similar, editable without a rebuild.

**M8 Operations monitoring**

Position: runtime monitoring and in-app messages for long-term operation.

- FR-M8-01 Runtime monitoring — queue length, GPU memory, disk usage and job failure rate.
- FR-M8-02 Messages and alerts — capture failures, job failures and finished reports pushed by role.

### 3.2 Requirement list

Twenty-nine items: 11 at P0, 15 at P1 and 3 at P2. P0 is the chain that must run live at the defence; P1 completes the experience; P2 leaves the baseline entirely if time runs short, and dropping it requires updating the traceability matrix and the acceptance items in the same change.

**Table 3-1 Functional requirements (29)**

| ID | Module | Function | Priority | Origin |
|---|---|---|---|---|
| FR-M1-01 | M1 | Sign-in and session | P0 | carried over |
| FR-M1-02 | M1 | Roles and permissions | P0 | rewritten |
| FR-M1-03 | M1 | Account management and reset | P1 | carried over |
| FR-M1-04 | M1 | Operation log and audit | P1 | carried over |
| FR-M2-01 | M2 | Single-frame capture and registration | P0 | rewritten |
| FR-M2-02 | M2 | Scheduled and continuous capture | P1 | rewritten |
| FR-M2-03 | M2 | Quality scoring and retake | P0 | new |
| FR-M2-04 | M2 | Batch and image search | P1 | carried over |
| FR-M2-05 | M2 | Retention and cleanup | P2 | carried over |
| FR-M3-01 | M3 | Immediate detection | P0 | rewritten |
| FR-M3-02 | M3 | Batch detection and queue | P0 | rewritten |
| FR-M3-03 | M3 | Detection parameters | P1 | carried over |
| FR-M3-04 | M3 | Result browsing and counting | P0 | carried over |
| FR-M3-05 | M3 | Export | P1 | carried over |
| FR-M4-01 | M4 | Review bench | P0 | carried over |
| FR-M4-02 | M4 | Review trail and versions | P1 | carried over |
| FR-M4-03 | M4 | Hard-example set | P1 | rewritten |
| FR-M4-04 | M4 | Dataset export | P1 | carried over |
| FR-M5-01 | M5 | Species composition | P1 | carried over |
| FR-M5-02 | M5 | Site and time distribution | P1 | carried over |
| FR-M5-03 | M5 | Trend and comparison | P2 | carried over |
| FR-M5-04 | M5 | Inspection report | P1 | rewritten |
| FR-M6-01 | M6 | Version registration | P0 | carried over |
| FR-M6-02 | M6 | Activation and rollback | P1 | carried over |
| FR-M6-03 | M6 | Experiments and metric comparison | P0 | new |
| FR-M6-04 | M6 | Species dictionary and thresholds | P0 | merged |
| FR-M7-01 | M7 | System parameters | P1 | carried over |
| FR-M8-01 | M8 | Runtime monitoring | P1 | rewritten |
| FR-M8-02 | M8 | Messages and alerts | P2 | carried over |

### 3.3 Detailed requirements

Each requirement states description, input, processing, output, business rules and acceptance points. The last two are the handles for review and testing: the rules answer "what must be refused", the acceptance points answer "how we prove it was done right".

#### 3.3.1 M1 User and permission management

**Table 3-2 FR-M1-01 Sign-in and session**

| Attribute | Content |
|---|---|
| ID | FR-M1-01 |
| Function | Sign-in and session |
| Priority | P0 (origin: carried over) |
| Description | Sign-in by phone or email, verifying a CAPTCHA and the password, issuing an access token (8 h, no refresh token). |
| Input | Phone or email, password, CAPTCHA |
| Processing | Verify CAPTCHA → look up the account → verify the password hash → check lockout → issue a JWT (8 h, no refresh token) |
| Output | Access token, basic user details, role code; on failure the specific reason and remaining lockout time |
| Business rules | Password 8-20 characters with letters and digits; five consecutive failures lock the account for 15 minutes; passwords stored salted and hashed, never in clear; only enabled accounts may sign in |
| Acceptance | After five wrong attempts the account locks and shows the remaining time; the password column holds a hash; a correct password is still refused while locked |

**Table 3-3 FR-M1-02 Roles and permissions**

| Attribute | Content |
|---|---|
| ID | FR-M1-02 |
| Function | Roles and permissions |
| Priority | P0 (origin: rewritten) |
| Description | Controls functionality and data access by the four roles, enforced on the server. |
| Input | Request path, HTTP method, current role code |
| Processing | Match the route against the permission matrix → allow on a hit, return 403 otherwise → write a rejection log |
| Output | The endpoint response, or a uniform 403 |
| Business rules | Hiding a menu is cosmetic only; the server must check again; capture endpoints accept only the local process and are never exposed; algorithm and configuration endpoints are restricted to the algorithm engineer and administrator |
| Acceptance | A collector calling the model activation endpoint receives 403 and the attempt is logged; an unauthenticated call to a capture endpoint receives 401 |

**Table 3-4 FR-M1-03 Account management and reset**

| Attribute | Content |
|---|---|
| ID | FR-M1-03 |
| Function | Account management and reset |
| Priority | P1 (origin: carried over) |
| Description | Administrators create, disable and restore accounts and reset passwords; one account per person. |
| Input | Name, phone, role, initial password, enabled state |
| Processing | Check phone uniqueness and format → create the account with the initial password → record the operator → on disable, invalidate issued tokens immediately |
| Output | Account list, state change result, one-time initial password |
| Business rules | Phone numbers are globally unique; a disabled account keeps all history but cannot sign in; the built-in administrator cannot be deleted; the first sign-in after a reset forces a change |
| Acceptance | A disabled account cannot sign in yet its detection history stays searchable; saving a duplicate phone number is refused with an "already exists" message |

**Table 3-5 FR-M1-04 Operation log and audit**

| Attribute | Content |
|---|---|
| ID | FR-M1-04 |
| Function | Operation log and audit |
| Priority | P1 (origin: carried over) |
| Description | Records sign-in, review, model activation and parameter changes, searchable by person, time and object. |
| Input | Operator, time, module, action type, object type and ID, before and after values, source IP |
| Processing | Middleware intercepts key endpoints → writes to the log table asynchronously → exposes search and export |
| Output | Filterable log list, single-entry detail, CSV export |
| Business rules | The log is append-only: no edits, no deletes; 180 days online; deletions, reviews, activations and parameter changes must record before and after values |
| Acceptance | Any review can be traced to an operator with before and after values; no endpoint can delete a log entry |

#### 3.3.2 M2 Capture and quality control

**Table 3-6 FR-M2-01 Single-frame capture and registration**

| Attribute | Content |
|---|---|
| ID | FR-M2-01 |
| Function | Single-frame capture and registration |
| Priority | P0 (origin: rewritten) |
| Description | Grabs one frame from the local camera, scores its quality and registers it; the only data source for detection jobs. |
| Input | Session ID, site code, capture timestamp, exposure and gain, JPEG frame data |
| Processing | Check the camera is available and exposure locked → check the timestamp is within 5 s of server time → compute the quality score → write to site/date/batch directories → insert the image row and link the batch |
| Output | Resource code, quality score and verdict, thumbnail |
| Business rules | A frame that was never registered cannot enter the detection queue; a frame with the same device and timestamp is idempotent; a frame below the quality threshold is stored but not detected, and a retake is prompted |
| Acceptance | With the capture end closed there is no image source available anywhere in the system; a frame more than 5 s off is refused with a recorded reason; grabbing the same frame twice produces one record |

**Table 3-7 FR-M2-02 Scheduled and continuous capture**

| Attribute | Content |
|---|---|
| ID | FR-M2-02 |
| Function | Scheduled and continuous capture |
| Priority | P1 (origin: rewritten) |
| Description | Triggers capture automatically at a fixed interval to form continuous batches for long observation. |
| Input | Start time, interval, number of captures, site, device |
| Processing | Build the schedule → trigger on time → register batch by batch → stop at the count or on manual stop |
| Output | Schedule list, execution records and failure reasons |
| Business rules | Minimum interval 5 minutes; schedules on one device must not overlap; schedules resume after a restart |
| Acceptance | A schedule of ten minutes and six captures produces six batches; an unavailable camera marks that run failed with a reason |

**Table 3-8 FR-M2-03 Quality scoring and retake**

| Attribute | Content |
|---|---|
| ID | FR-M2-03 |
| Function | Quality scoring and retake |
| Priority | P0 (origin: new) |
| Description | Scores sharpness, brightness and colour cast on a registered frame and keeps low scores out of the queue. |
| Input | Image frame, quality threshold configuration |
| Processing | Compute Laplacian variance (sharpness), mean brightness and channel mean difference (colour cast) → weighted score → below threshold marks "needs retake" |
| Output | Total score, the three component values, verdict |
| Business rules | Weights 0.5 sharpness, 0.3 brightness, 0.2 colour cast; below 60 the frame is stored but not detected; one click triggers a retake |
| Acceptance | A deliberately defocused frame scores below 60 and does not enter the queue; a retake becomes its own record in the same batch, marked as a retake |

**Table 3-9 FR-M2-04 Batch and image search**

| Attribute | Content |
|---|---|
| ID | FR-M2-04 |
| Function | Batch and image search |
| Priority | P1 (origin: carried over) |
| Description | Searches batches by site, time range, device and state, and drills down to frames. |
| Input | Site, time range, device, batch state, paging |
| Processing | Build the query → order by capture time descending → return batches → allow drilling into a frame grid |
| Output | Batch list, frame grid, a frame selection for batch actions |
| Business rules | 24 per page by default; batches and frames form two levels; thumbnails are generated asynchronously with a placeholder until ready |
| Acceptance | The four filters combine correctly; a batch drills down to frames and the selection carries into job creation |

**Table 3-10 FR-M2-05 Retention and cleanup**

| Attribute | Content |
|---|---|
| ID | FR-M2-05 |
| Function | Retention and cleanup |
| Priority | P2 (origin: carried over) |
| Description | Removes thumbnails, intermediate files and expired result images after the retention period; originals are never removed automatically. |
| Input | Retention days, object type, mode (automatic or manual) |
| Processing | Scan expired files → build a cleanup list → delete and null the references → write a cleanup log |
| Output | Cleanup list, space freed, current disk usage |
| Business rules | Original frames are never auto-deleted; intermediate files default to 7 days; a reviewable list must exist before deletion |
| Acceptance | After a manual cleanup the references are null and disk usage drops; originals survive under the default policy |

#### 3.3.3 M3 Detection

**Table 3-11 FR-M3-01 Immediate detection**

| Attribute | Content |
|---|---|
| ID | FR-M3-01 |
| Function | Immediate detection |
| Priority | P0 (origin: rewritten) |
| Description | Detects one frame and returns class, position, confidence and an overlay end to end. |
| Input | Image resource code, model version, confidence and IoU thresholds |
| Processing | Verify frame origin and quality → preprocess (colour correction, dehazing) → infer → write the job and target rows → return |
| Output | Result list, annotated image, per-frame time |
| Business rules | Only frames registered through capture are accepted; end to end within 1.5 s on GPU; boxes below threshold are not returned but stay in the database |
| Acceptance | From trigger to boxes on screen within 3 s; a local image that did not come from capture is refused with a "source mismatch" message |

**Table 3-12 FR-M3-02 Batch detection and queue**

| Attribute | Content |
|---|---|
| ID | FR-M3-02 |
| Function | Batch detection and queue |
| Priority | P0 (origin: rewritten) |
| Description | Queues a set of frames for detection with progress, cancel and retry. |
| Input | Batch ID or frame list, model version, parameters |
| Processing | Create and enqueue the job → infer frame by frame → update progress live → record failures and continue → summarise at the end |
| Output | Job progress, success and failure counts, failure list |
| Business rules | At most 500 frames per job; at most two jobs running at once; cancelling keeps results already produced |
| Acceptance | A 100-frame job updates progress live; a cancel takes effect within 5 s and nothing new is processed; failed frames can be retried individually |

**Table 3-13 FR-M3-03 Detection parameters**

| Attribute | Content |
|---|---|
| ID | FR-M3-03 |
| Function | Detection parameters |
| Priority | P1 (origin: carried over) |
| Description | Confidence, IoU, per-image limit and class filter for a job, frozen with it. |
| Input | Confidence threshold, IoU threshold, maximum detections per image, class set |
| Processing | Validate ranges → save as job parameters or a saved profile → load at inference |
| Output | Parameters in force for this job, saved profile list |
| Business rules | Confidence 0.1-0.9; IoU 0.1-0.9; at most 300 per image; parameters cannot change once the job exists |
| Acceptance | Changing confidence changes the number of results on the same frame; the parameters recorded on the job match those used |

**Table 3-14 FR-M3-04 Result browsing and counting**

| Attribute | Content |
|---|---|
| ID | FR-M3-04 |
| Function | Result browsing and counting |
| Priority | P0 (origin: carried over) |
| Description | Shows results as boxes over the original image and summarises the count per class. |
| Input | Job ID, class filter, confidence range |
| Processing | Query targets → render the overlay → aggregate counts by class → mark low-confidence targets |
| Output | Result image, target list, per-class counts and mean confidence |
| Business rules | The count is the de-duplicated number of targets; within a frame, duplicates are merged by track ID; low-confidence targets are marked separately |
| Acceptance | The page count equals the number of list rows; switching the class filter updates count and chart together |

**Table 3-15 FR-M3-05 Export**

| Attribute | Content |
|---|---|
| ID | FR-M3-05 |
| Function | Export |
| Priority | P1 (origin: carried over) |
| Description | Exports results as structured files and boxed images for external analysis and archiving. |
| Input | Job ID, format (CSV / JSON / annotated image) |
| Processing | Generate the file → write to the export directory → return a download URL → log the action |
| Output | File and download link, number of rows |
| Business rules | Coordinates normalised; CSV columns fixed to image name, class, confidence and four coordinates; the row count must match the page |
| Acceptance | The exported CSV has as many rows as the page shows results; Excel opens it with Chinese intact |

#### 3.3.4 M4 Review and feedback

**Table 3-16 FR-M4-01 Review bench**

| Attribute | Content |
|---|---|
| ID | FR-M4-01 |
| Function | Review bench |
| Priority | P0 (origin: carried over) |
| Description | Adds, deletes and edits boxes and classes on the result image, producing a new reviewed result on submit. |
| Input | Review queue, canvas edits (add, delete, relabel, drag), conclusion |
| Processing | Load the original and automatic results → edit on the canvas → submit to create a review version → update counts and statistics |
| Output | Reviewed result, change list, current count |
| Business rules | Review applies only to captured frames; every submit creates a new version; every edit records operator and time |
| Acceptance | Deleting a false box lowers the count by one; drawing a missed box raises it by one; the automatic result stays viewable after submit |

**Table 3-17 FR-M4-02 Review trail and versions**

| Attribute | Content |
|---|---|
| ID | FR-M4-02 |
| Function | Review trail and versions |
| Priority | P1 (origin: carried over) |
| Description | Keeps every review as a version, with diff between versions and rollback. |
| Input | Reviewer, conclusion, set of edits |
| Processing | Write a version record → compute the diff against the previous version → allow rollback, which itself creates a version |
| Output | Version timeline, diff view, rollback result |
| Business rules | Version numbers increase monotonically; rollback never deletes history; only analysts, algorithm engineers and administrators may review |
| Acceptance | Two reviews produce two versions; after rollback the result matches the target version exactly and the history remains |

**Table 3-18 FR-M4-03 Hard-example set**

| Attribute | Content |
|---|---|
| ID | FR-M4-03 |
| Function | Hard-example set |
| Priority | P1 (origin: rewritten) |
| Description | Collects low-confidence, human-corrected and cross-model-disagreement samples automatically for the algorithm staff to handle first. |
| Input | Low-confidence results, corrected results, results where models disagree |
| Processing | Tag automatically by origin → gather into the pool → allow manual selection and removal |
| Output | Hard-example list, origin reason, batch |
| Business rules | Three origin types, all filterable; a frame enters the pool once; removal records a reason |
| Acceptance | Every sample corrected in review appears in the pool with its origin tag; removed samples no longer appear |

**Table 3-19 FR-M4-04 Dataset export**

| Attribute | Content |
|---|---|
| ID | FR-M4-04 |
| Function | Dataset export |
| Priority | P1 (origin: carried over) |
| Description | Exports a YOLO-format dataset for a sample range, split ratio and seed, so training is reproducible. |
| Input | Sample range (hard-example pool / batch / all), train-valid-test ratio, seed |
| Processing | Sample → split by ratio → write images and labels directories plus data.yaml → bundle for download → record a snapshot |
| Output | Dataset archive, split statistics, snapshot ID |
| Business rules | Ratios must sum to 1; the same seed must produce an identical file list; unreviewed automatic results never enter the training set |
| Acceptance | Two exports with one seed produce identical file lists; split statistics match the actual file counts |

#### 3.3.5 M5 Statistics and reports

**Table 3-20 FR-M5-01 Species composition**

| Attribute | Content |
|---|---|
| ID | FR-M5-01 |
| Function | Species composition |
| Priority | P1 (origin: carried over) |
| Description | Summarises count, share and mean confidence by class over time, site and statistical basis. |
| Input | Time range, site, basis (automatic results or post-review results) |
| Processing | Aggregate counts by class → compute share and mean confidence → render pie chart and ranking |
| Output | Pie chart, ranking table, totals |
| Business rules | The basis is switchable and the chart must state which one is in use; disabled species are excluded; shares total 100 % |
| Acceptance | Switching the basis changes the numbers and the label together; class shares total 100 % |

**Table 3-21 FR-M5-02 Site and time distribution**

| Attribute | Content |
|---|---|
| ID | FR-M5-02 |
| Function | Site and time distribution |
| Priority | P1 (origin: carried over) |
| Description | Shows target density by site and date, identifies dense areas and supports drilling down. |
| Input | Time range, site set, species |
| Processing | Aggregate by site and date → render heat map and density ranking → click through to batches |
| Output | Heat map, density ranking, drill-down detail |
| Business rules | With no data, show an empty state rather than a blank chart; a disabled site keeps its history |
| Acceptance | Heat-map values match the ranking table; an empty state appears when there is no data |

**Table 3-22 FR-M5-03 Trend and comparison**

| Attribute | Content |
|---|---|
| ID | FR-M5-03 |
| Function | Trend and comparison |
| Priority | P2 (origin: carried over) |
| Description | Counts change by day, week and month, with period-on-period and year-on-year rates. |
| Input | Species, granularity, time range, comparison period |
| Processing | Aggregate the series → compute the rates → mark significant swings |
| Output | Line chart, rates, swing markers |
| Business rules | With no baseline data the rate shows "—" rather than 0; fewer than three valid points produces no trend conclusion |
| Acceptance | Rates reconcile by hand against the detail; a missing baseline shows "—" |

**Table 3-23 FR-M5-04 Inspection report**

| Attribute | Content |
|---|---|
| ID | FR-M5-04 |
| Function | Inspection report |
| Priority | P1 (origin: rewritten) |
| Description | Summarises detection over a period and site range and renders a downloadable report from a template. |
| Input | Period, site range, template |
| Processing | Gather job, species, site and quality data → render charts through the template → produce a Markdown report → record history |
| Output | Report file, generation record, download link |
| Business rules | The footer must state the model version and statistical basis; repeated generation keeps history; a failure must not leave a half-written file |
| Acceptance | Report figures match the dashboard; the footer carries version and basis; earlier versions stay downloadable |

#### 3.3.6 M6 Models and experiments

**Table 3-24 FR-M6-01 Version registration**

| Attribute | Content |
|---|---|
| ID | FR-M6-01 |
| Function | Version registration |
| Priority | P0 (origin: carried over) |
| Description | Registers weights, training provenance, metrics and scope of use as a deployment candidate. |
| Input | Version name, weights path, dataset snapshot, mAP, recall, FPS, parameter count, notes |
| Processing | Check the name is unique and the weights exist → register as candidate → compute the metric gap against the live version |
| Output | Version list, metric card, candidate state |
| Business rules | Names are unique; a version without metrics cannot be registered as a candidate; missing weights are refused |
| Acceptance | Saving without mAP is refused; saving a duplicate name is refused with an "already exists" message |

**Table 3-25 FR-M6-02 Activation and rollback**

| Attribute | Content |
|---|---|
| ID | FR-M6-02 |
| Function | Activation and rollback |
| Priority | P1 (origin: carried over) |
| Description | Switches a candidate to the live model and rolls back to the previous version. |
| Input | Target version, operator, change note |
| Processing | Check the version state → retire the current live version → mark the new one live → write the change log |
| Output | Current live version, change record, affected scope |
| Business rules | Exactly one live model at a time; a live model cannot be deleted; activation requires an evaluation record |
| Acceptance | New jobs after activation use the new version and record it; after rollback the job detail shows the rolled-back version |

**Table 3-26 FR-M6-03 Experiments and metric comparison**

| Attribute | Content |
|---|---|
| ID | FR-M6-03 |
| Function | Experiments and metric comparison |
| Priority | P0 (origin: new) |
| Description | Records each training run's dataset snapshot, hyperparameters and metrics, and compares it with the baseline in one table. |
| Input | Experiment name, dataset snapshot, split, seed, epochs, batch size, learning rate, metrics |
| Processing | Save the record → mark it baseline or not → build the comparison table → filter by dataset |
| Output | Experiment list, comparison table, best-experiment marker |
| Business rules | Comparison columns fixed to mAP@0.5, mAP@0.5:0.95, mean recall, FPS and parameter count; the baseline cannot be deleted; the same dataset and seed must reproduce |
| Acceptance | Improved and baseline runs compare directly in one table; two runs with identical parameters differ by less than 1 % |

**Table 3-27 FR-M6-04 Species dictionary and per-class thresholds**

| Attribute | Content |
|---|---|
| ID | FR-M6-04 |
| Function | Species dictionary and per-class thresholds |
| Priority | P0 (origin: merged) |
| Description | Maintains Chinese name, Latin name, class code, category and per-class confidence threshold. |
| Input | Chinese name, Latin name, class code, category (commercial / predator / environmental), threshold, counted-in-statistics flag |
| Processing | Check the class code matches the model labels file → save → sync to the inference configuration |
| Output | Dictionary list, current thresholds, mapping |
| Business rules | Class codes are unique and must exist in the model labels file; thresholds 0.1-0.9; disabled species leave statistics but keep their history |
| Acceptance | A mismatched class code is refused with the differing entries listed; new jobs use a changed threshold |

#### 3.3.7 M7 System configuration

**Table 3-28 FR-M7-01 System parameters**

| Attribute | Content |
|---|---|
| ID | FR-M7-01 |
| Function | System parameters |
| Priority | P1 (origin: carried over) |
| Description | Maintains retention days, concurrency limit, default thresholds and the alert scan interval. |
| Input | Retention days, concurrency limit, default confidence, quality threshold, scan interval |
| Processing | Validate ranges → write to the configuration file and bump its version → record the change log |
| Output | Current parameters, pending parameters, change records |
| Business rules | Parameters are externalised, so a change needs no rebuild; changes to key parameters must be logged with before and after values; invalid values are refused |
| Acceptance | A new concurrency limit constrains new jobs; a parameter change shows before, after and operator in the log |

#### 3.3.8 M8 Operations monitoring

**Table 3-29 FR-M8-01 Runtime monitoring**

| Attribute | Content |
|---|---|
| ID | FR-M8-01 |
| Function | Runtime monitoring |
| Priority | P1 (origin: rewritten) |
| Description | Shows job queue, GPU memory, disk usage and job failure rate, with a warning past a threshold. |
| Input | No manual input; sampled automatically |
| Processing | Sample runtime metrics every 30 s → compute the failure rate → mark anomalies past the threshold |
| Output | Monitoring panel, metric trends, anomaly notices |
| Business rules | Only runtime metrics are collected, never personal data; thresholds come from system parameters; the panel refreshes every 30 s |
| Acceptance | Submitting a large batch visibly moves queue length and failure rate; disk usage past its threshold turns the item red with a note |

**Table 3-30 FR-M8-02 Messages and alerts**

| Attribute | Content |
|---|---|
| ID | FR-M8-02 |
| Function | Messages and alerts |
| Priority | P2 (origin: carried over) |
| Description | Generates in-app messages by role for capture failures, job failures and finished reports. |
| Input | Event type, related object, target role |
| Processing | Event fires → message generated per role → frontend polls the unread count → mark as read supported |
| Output | Unread count, message list, read state |
| Business rules | Same type and object collapse into one message within an hour; messages kept 30 days; messages never block the main flow |
| Acceptance | A capture failure produces one message and increments the unread count; repeated failures within an hour add nothing |

### 3.4 Use cases

Nine use cases cover the chain from capture to report export. Each maps to specific requirement IDs; Appendix A holds the closed-loop trace.

**Table 3-31 Use case index**

| ID | Use case | Actor | Related requirements |
|---|---|---|---|
| UC-01 | Capture one frame and score its quality | Collector | FR-M2-01, FR-M2-03 |
| UC-02 | Schedule an inspection capture and view batches | Collector | FR-M2-02, FR-M2-04 |
| UC-03 | Detect a single frame and view results | Collector | FR-M3-01, FR-M3-03, FR-M3-04 |
| UC-04 | Batch detection and progress monitoring | Collector | FR-M3-02, FR-M3-03 |
| UC-05 | Correct a false positive and a miss, feeding the hard-example pool | Analyst | FR-M4-01, FR-M4-02, FR-M4-03 |
| UC-06 | Export a dataset and start a training run | Algorithm engineer | FR-M4-04, FR-M6-03, FR-M6-01 |
| UC-07 | Evaluate an improved model and deploy it | Algorithm engineer | FR-M6-01, FR-M6-02, FR-M3-01 |
| UC-08 | View species statistics and export an inspection report | Analyst | FR-M5-01, FR-M5-02, FR-M5-04 |
| UC-09 | Diagnose and handle a capture quality problem | Administrator / collector | FR-M8-02 |

#### 3.4.01 UC-01 Capture one frame and score its quality

**Table 3-32 UC-01**

| Attribute | Content |
|---|---|
| ID | UC-01 |
| Name | Capture one frame and score its quality |
| Main actor | Collector |
| Precondition | Camera connected, exposure and white balance locked |
| Main flow | 1. Mount the camera on the outer wall and open the capture page / 2. Press "start capture"; the system grabs one frame / 3. The system computes sharpness, brightness and colour cast and scores 86 / 4. The score passes, the frame is stored as site/date/index with a resource code / 5. The page shows the thumbnail, score and a "detectable" marker |
| Alternative flows | 1. Too dark: prompt to turn on the fill light and retake / 2. Below 60: stored but marked "needs retake", kept out of the queue / 3. Camera not connected: report the device unavailable, create no record |
| Postcondition | One capture record exists and can be sent straight to detection |
| Requirements | FR-M2-01, FR-M2-03 |

#### 3.4.02 UC-02 Schedule an inspection capture and view batches

**Table 3-33 UC-02**

| Attribute | Content |
|---|---|
| ID | UC-02 |
| Name | Schedule an inspection capture and view batches |
| Main actor | Collector |
| Precondition | Device online, site configured |
| Main flow | 1. Set start time, a 10-minute interval and 6 captures on the schedule page / 2. The system checks for overlap on the same device and saves / 3. Triggers fire on time and register batch by batch / 4. The collector sees 6 batches and their frame counts |
| Alternative flows | 1. Overlap with an existing schedule: refused with the conflicting window / 2. One trigger fails: that batch is marked failed with a reason / 3. Manual stop: captured batches are kept, remaining ones cancelled |
| Postcondition | 6 batches exist, each with the planned frame count |
| Requirements | FR-M2-02, FR-M2-04 |

#### 3.4.03 UC-03 Detect a single frame and view results

**Table 3-34 UC-03**

| Attribute | Content |
|---|---|
| ID | UC-03 |
| Name | Detect a single frame and view results |
| Main actor | Collector |
| Precondition | Frame registered and quality-passed, live model available |
| Main flow | 1. Press "detect" on the image detail page / 2. The system loads default thresholds and runs preprocessing and inference / 3. The page returns the overlay and the target list / 4. The collector filters by class and reads the count |
| Alternative flows | 1. Frame failed quality: the button is disabled with a retake prompt / 2. Model failed to load: job marked failed, prompt to contact the administrator / 3. Empty result: show "no targets detected" rather than a blank page |
| Postcondition | One immediate detection job and its targets exist, with the elapsed time recorded |
| Requirements | FR-M3-01, FR-M3-03, FR-M3-04 |

#### 3.4.04 UC-04 Batch detection and progress monitoring

**Table 3-35 UC-04**

| Attribute | Content |
|---|---|
| ID | UC-04 |
| Name | Batch detection and progress monitoring |
| Main actor | Collector |
| Precondition | A batch of 100 frames, live model available |
| Main flow | 1. Select the batch and start detection / 2. The system creates and queues the job and shows the queue position / 3. Progress updates live / 4. On completion, read the summary and the failure list |
| Alternative flows | 1. Two jobs already running: the new one queues with an estimated wait / 2. A corrupted frame: marked failed, the rest continue / 3. Cancel: stops within 5 s, results already produced are kept |
| Postcondition | The job is complete and its success count equals the batch frame count |
| Requirements | FR-M3-02, FR-M3-03 |

#### 3.4.05 UC-05 Correct a false positive and a miss, feeding the hard-example pool

**Table 3-36 UC-05**

| Attribute | Content |
|---|---|
| ID | UC-05 |
| Name | Correct a false positive and a miss, feeding the hard-example pool |
| Main actor | Analyst |
| Precondition | Low-confidence results are waiting for review |
| Main flow | 1. Open the review bench and the review queue / 2. Delete 4 boxes that called a rock a sea cucumber / 3. Draw 2 boxes for missed sea cucumbers / 4. Submit; the system creates a new version and updates counts / 5. The 6 corrected frames enter the hard-example pool |
| Alternative flows | 1. A box dragged off the canvas is clamped to the image / 2. A mistake: undo, or roll back to the previous version / 3. Leaving early: submitted edits apply, unsubmitted ones are discarded |
| Postcondition | A review version and change list exist; the pool gains 6 samples with their origin |
| Requirements | FR-M4-01, FR-M4-02, FR-M4-03 |

#### 3.4.06 UC-06 Export a dataset and start a training run

**Table 3-37 UC-06**

| Attribute | Content |
|---|---|
| ID | UC-06 |
| Name | Export a dataset and start a training run |
| Main actor | Algorithm engineer |
| Precondition | The pool has samples and historical results are reviewed |
| Main flow | 1. Choose the pool as the range, a 7:2:1 split and seed 42 / 2. The system builds the YOLO directories, bundles them and records a snapshot ID / 3. Train locally, then register the experiment / 4. Compare against the baseline in the experiment table |
| Alternative flows | 1. Ratios do not sum to 1: refused with a message / 2. Unreviewed samples exist: export refused and listed / 3. Repeat export: identical file list, reusable directly |
| Postcondition | A dataset archive and snapshot ID exist; the experiment table gains a row comparable with the baseline |
| Requirements | FR-M4-04, FR-M6-03, FR-M6-01 |

#### 3.4.07 UC-07 Evaluate an improved model and deploy it

**Table 3-38 UC-07**

| Attribute | Content |
|---|---|
| ID | UC-07 |
| Name | Evaluate an improved model and deploy it |
| Main actor | Algorithm engineer |
| Precondition | The improved run finished and meets the threshold |
| Main flow | 1. Register the candidate version with its metrics / 2. The system checks the weights exist and the metrics are complete / 3. Activate; the previous live version retires automatically / 4. Create a job and confirm it uses the new version |
| Alternative flows | 1. mAP below 0.70: registration as candidate refused, metrics shown / 2. Weights path missing: registration fails / 3. Metrics look wrong after activation: roll back and jobs return to the old version |
| Postcondition | The live version switched, job detail records the new number, the change is logged |
| Requirements | FR-M6-01, FR-M6-02, FR-M3-01 |

#### 3.4.08 UC-08 View species statistics and export an inspection report

**Table 3-39 UC-08**

| Attribute | Content |
|---|---|
| ID | UC-08 |
| Name | View species statistics and export an inspection report |
| Main actor | Analyst |
| Precondition | The current month has completed jobs and reviewed results |
| Main flow | 1. Open the dashboard, choose the last 30 days and all sites / 2. Switch the basis to "post-review" and the charts refresh / 3. Go to the report page and choose period and template / 4. Generate, download, and check the footer's model version and basis |
| Alternative flows | 1. A range with no data shows an empty state / 2. Rendering fails: name the failing step and leave no partial file / 3. Regenerating keeps earlier versions |
| Postcondition | A report file exists whose figures match the dashboard |
| Requirements | FR-M5-01, FR-M5-02, FR-M5-04 |

#### 3.4.09 UC-09 Diagnose and handle a capture quality problem

**Table 3-40 UC-09**

| Attribute | Content |
|---|---|
| ID | UC-09 |
| Name | Diagnose and handle a capture quality problem |
| Main actor | Collector / administrator |
| Precondition | Consecutive frames are marked for retake, or brightness swings past the threshold |
| Main flow | 1. The collector filters the quality list by "needs retake" / 2. The system shows the three component values and a suggestion: too dark, too blue, or too soft / 3. The collector adjusts the lamp angle or re-locks exposure and retakes / 4. The administrator changes the quality threshold in system parameters, logged / 5. The retake becomes its own record, marked as a retake |
| Alternative flows | 1. Still failing after adjustment: mark the device faulty and notify the administrator / 2. The threshold is lowered to pass: before and after are logged for review / 3. The camera is held by another process: prompt to release it and retry |
| Postcondition | The quality problem has a handling record and threshold changes are traceable |
| Requirements | FR-M2-03, FR-M7-01, FR-M1-04 |

### 3.5 Algorithm requirements

This section answers what the "improved" in the title actually changes. The principle: only improvements that can finish inside a week, be explained in one table, and be pointed at during the defence. So no new architecture — three points, each with an independent contribution and each ablatable.

#### 3.5.1 Baseline and training conditions

The baseline is Ultralytics YOLOv8n at 640×640, 100 epochs, batch 16, initial learning rate 0.01, seed fixed at 42, on the four DUO classes. The class choice is deliberate: sea cucumber, sea urchin and scallop are the main commercial species of a marine ranch, and starfish is the main predator of scallop farming; all four are annotated in DUO, so the existing labels are reusable. Every baseline setting goes into the experiment table, and each later run changes exactly one thing so the comparison stays clean.

#### 3.5.2 Three improvements

**Table 3-41 The three improvements**

| ID | Improvement | Layer | Method | Expected effect |
|---|---|---|---|---|
| AR-01 | Underwater colour correction | Data | Grey-world white balance + red-channel compensation + CLAHE; the same operators on training and inference, switchable | Reduces the blue-green cast and haze, raising recall on small and low-contrast targets |
| AR-02 | Attention | Structure | An EMA attention block between the Neck output and the detection head; backbone untouched | Strengthens response on targets, suppresses false positives on rock and weed |
| AR-03 | Bounding-box loss | Optimisation | Replace CIoU with WIoU v3 to reduce the pull of low-quality samples | More stable localisation, more robust to occlusion and blur |

#### 3.5.3 Experiments and ablation

Five runs, each adding one piece; E0 is the control and E4 adds in-house fine-tuning on top of the full scheme. The seed is fixed, and two runs of one configuration must differ by less than 1 %, otherwise the result is not reproducible.

**Table 3-42 Ablation design**

| Run | Change | Key configuration | Loss | Training set | Purpose |
|---|---|---|---|---|---|
| E0 | Baseline: YOLOv8n | Original images | CIoU | Public training split | Control |
| E1 | + colour correction (AR-01) | Grey-world + red compensation + CLAHE | CIoU | Same | Preprocessing contribution |
| E2 | + attention (AR-01 + AR-02) | As E1 | CIoU | Same | Structural contribution |
| E3 | + box loss (AR-01 to 03) | As E1 | WIoU v3 | Same | Full scheme |
| E4 | Full scheme + in-house fine-tuning | As E1 | WIoU v3 | Public split + 300 in-house tank frames | Closed loop and generalisation |

#### 3.5.4 Metrics and thresholds

Acceptance uses a fixed test set. The metric definitions appear here once and nowhere else; other chapters refer to this section.

**Table 3-43 Algorithm metrics and thresholds**

| ID | Metric | Target | Note |
|---|---|---|---|
| AL-01 | mAP@0.5 | ≥ 0.75 | Fixed test set, four classes, IoU = 0.5 |
| AL-02 | mAP@0.5:0.95 | ≥ 0.45 | Averaged over IoU 0.5 to 0.95 in steps of 0.05 |
| AL-03 | Per-class recall | ≥ 0.75 for all four | Computed per class; no average may hide one very low class |
| AL-04 | Improvement | mAP@0.5 at least +0.03 over baseline | Same data, epochs and seed; only the model changes |
| AL-05 | Inference speed | ≥ 90 % of baseline | Same hardware and batch, mean of 100 images |
| AL-06 | Parameters | Increase ≤ 20 % | From the model summary |
| AL-07 | Count deviation | ≤ 15 % | Against manual reading on the same clip, de-duplicated |

#### 3.5.5 Delivery form of a model

Every activation delivers five things together: `best.pt`, the exported `best.onnx`, `labels.txt` (whose order must match the species dictionary), the training log and the evaluation report. One position out of order misaligns every result, so the dictionary save validates `labels.txt` and refuses on a mismatch.

## 4 Data requirements

### 4.1 Core entities

Fourteen tables. Against the first draft, the site table, annotation table, dataset-version table,
alert table and training-job table are gone; the training-experiment table and the message table are new. Site is now a column on the image table, the dataset snapshot and training parameters merged into the experiment table, and annotation moved to an offline tool so no longer needs a table.

**Revision in V1.5.** Four tables were added after the skeleton was built on the nine. The merge of the
dataset snapshot into the experiment table assumed export and training happen together; they do not,
and a snapshot that no experiment references yet had nowhere to live, so `dataset` and `dataset_item`
now hold it — `dataset_item` also answers which frames trained a model, and lets a retained frame be
cleared rather than silently orphaning a snapshot (AC-09). `report` exists because the report history
is filtered by period, template and basis (FR-M5-04, AC-22); a pile of files cannot be queried, and the
audit log is not a domain index. `sys_param` exists because FR-M7-01 and AC-27 require parameter changes
to persist and stay auditable, which environment variables cannot do. The decision is recorded in ADR
08.

**Revision in V1.12.** A fourteenth table, `detect_task_item`, records the frames assigned to each
detection task when it is created — one row per frame, with its own state and box count — so a task's
work list is fixed rather than re-discovered, and a frame with no objects is recorded as done rather
than picked up again; the decision is recorded in ADR 12.

**Table 4-1 Entity list**

| Entity (table) | Name | Purpose | Fields |
|---|---|---|---|
| sys_user | User | Account, role and sign-in state; underpins authentication and permissions. | 13 |
| sys_log | Operation log | Audit record of key actions; append-only. | 10 |
| media_asset | Image asset | Captured frame with path, timestamp, exposure and quality score. | 18 |
| detect_task | Detection job | Model, parameters, progress and statistics for one job. | 16 |
| detect_object | Detected object | Class, confidence, coordinates and review state of one box. | 19 |
| species_dict | Species dictionary | Class code, names, category and per-class confidence threshold. | 10 |
| model_version | Model version | Weights, metrics and activation state. | 14 |
| train_experiment | Training experiment | Dataset snapshot, hyperparameters and metrics, with a baseline flag. | 18 |
| sys_message | Message | Role-targeted messages generated from events, with read state. | 10 |
| sys_param | Parameter | Runtime configuration as key/value pairs, with who changed it and when. | 7 |
| dataset | Dataset snapshot | An exported snapshot: split ratio, seed, size and manifest. | 9 |
| dataset_item | Snapshot item | One frame in one snapshot and the split it belongs to. | 5 |
| report | Inspection report | Period, template, basis, model version and the generated file. | 12 |
| detect_task_item | Task item | One frame assigned to one detection job, with its own state and box count. | 7 |

### 4.2 Data dictionary

Field level, one field per row, with types and constraints usable directly for schema creation. Every enumerated value written with a slash is stored as an integer and displayed in Chinese.

#### 4.2.1 sys_user

**Table 4-2 sys_user**

| Field | Type | Constraint / default | Note |
|---|---|---|---|
| user_id | BIGINT | PK, AUTO_INCREMENT | Primary key |
| username | VARCHAR(64) | UNIQUE, NOT NULL | Sign-in name |
| phone | VARCHAR(20) | UNIQUE, NULL | Phone, masked on display |
| email | VARCHAR(128) | UNIQUE, NULL | Email; phone or email required |
| password_hash | VARCHAR(128) | NOT NULL | Salted hash |
| salt | VARCHAR(32) | NOT NULL | Password salt |
| role_code | VARCHAR(16) | NOT NULL | observer / analyst / algo / admin |
| real_name | VARCHAR(64) | NOT NULL | Real name |
| status | SMALLINT | DEFAULT 1 | 1 enabled / 0 disabled |
| fail_count | SMALLINT | DEFAULT 0 | Consecutive sign-in failures |
| locked_until | TIMESTAMP | NULL | Lockout end |
| last_login_at | TIMESTAMP | NULL | Last sign-in |
| created_at | TIMESTAMP | DEFAULT now() | Created |

#### 4.2.2 sys_log

**Table 4-3 sys_log**

| Field | Type | Constraint / default | Note |
|---|---|---|---|
| log_id | BIGINT | PK, AUTO_INCREMENT | Primary key |
| user_id | BIGINT | FK→sys_user, NULL | Operator; null for system actions |
| module | VARCHAR(32) | NOT NULL | Module identifier |
| action | VARCHAR(32) | NOT NULL | Action: sign-in / review / activation / parameter change |
| target_type | VARCHAR(32) | NULL | Object type |
| target_id | VARCHAR(64) | NULL | Object ID |
| before_value | TEXT | NULL | Value before (JSON) |
| after_value | TEXT | NULL | Value after (JSON) |
| ip | VARCHAR(64) | NULL | Source IP |
| created_at | TIMESTAMP | DEFAULT now() | When it happened |

#### 4.2.3 media_asset

**Table 4-4 media_asset**

| Field | Type | Constraint / default | Note |
|---|---|---|---|
| asset_id | BIGINT | PK, AUTO_INCREMENT | Primary key |
| frame_id | VARCHAR(32) | UNIQUE, NOT NULL | Frame id, format YYYYMMDDTHHMMSS-mmmm |
| session_id | VARCHAR(32) | NOT NULL | Session ID, one value per continuous capture |
| point_code | VARCHAR(32) | NOT NULL | Monitoring site |
| file_path | VARCHAR(512) | NOT NULL | Relative file path |
| thumb_path | VARCHAR(512) | NULL | Thumbnail path |
| file_size | BIGINT | NOT NULL | Bytes |
| file_hash | CHAR(64) | NOT NULL | SHA-256, used for de-duplication |
| captured_at | TIMESTAMP | NOT NULL | Capture timestamp, UTC, millisecond precision |
| width | INT | NOT NULL | Width in pixels |
| height | INT | NOT NULL | Height in pixels |
| exposure_us | INT | NULL | Exposure time (µs) |
| gain_db | NUMERIC(5,2) | NULL | Gain (dB) |
| quality_score | SMALLINT | DEFAULT 0 | Total score 0-100 |
| quality_flag | SMALLINT | DEFAULT 0 | 0 pass / 1 needs retake |
| is_retake | SMALLINT | DEFAULT 0 | Whether this frame is a retake |
| turbidity_rel | SMALLINT | NULL | Relative turbidity 0-100, 0 clear; from the capture sensor |
| created_at | TIMESTAMP | DEFAULT now() | Registered at |

#### 4.2.4 detect_task

**Table 4-5 detect_task**

| Field | Type | Constraint / default | Note |
|---|---|---|---|
| task_id | BIGINT | PK, AUTO_INCREMENT | Primary key |
| task_code | VARCHAR(32) | UNIQUE, NOT NULL | Job code, rule DTyyMMdd-index |
| task_type | SMALLINT | NOT NULL | 1 immediate / 2 batch |
| model_version_id | BIGINT | FK→model_version | Model version used |
| asset_count | INT | NOT NULL | Number of frames |
| conf_thr | NUMERIC(4,2) | DEFAULT 0.50 | Confidence threshold |
| iou_thr | NUMERIC(4,2) | DEFAULT 0.45 | IoU threshold |
| max_det | INT | DEFAULT 100 | Maximum detections per image |
| class_filter | VARCHAR(256) | NULL | Class codes as a JSON array, NULL = all classes |
| status | SMALLINT | DEFAULT 0 | 0 queued / 1 running / 2 done / 3 failed / 4 cancelled |
| progress | SMALLINT | DEFAULT 0 | Progress percentage |
| obj_count | INT | DEFAULT 0 | Total objects |
| error_msg | VARCHAR(512) | NULL | Failure reason |
| created_by | BIGINT | FK→sys_user | Creator |
| created_at | TIMESTAMP | DEFAULT now() | Created |
| finished_at | TIMESTAMP | NULL | Finished |

#### 4.2.5 detect_object

**Table 4-6 detect_object**

| Field | Type | Constraint / default | Note |
|---|---|---|---|
| object_id | BIGINT | PK, AUTO_INCREMENT | Primary key |
| task_id | BIGINT | FK→detect_task, NOT NULL | Owning job |
| asset_id | BIGINT | FK→media_asset, NOT NULL | Owning frame |
| frame_id | VARCHAR(32) | NOT NULL | Frame id, denormalised for fast lookup |
| class_code | VARCHAR(32) | FK→species_dict, NOT NULL | Class code |
| confidence | NUMERIC(5,4) | NOT NULL | Confidence |
| x | NUMERIC(8,5) | NOT NULL | Box left edge (normalised) |
| y | NUMERIC(8,5) | NOT NULL | Box top edge (normalised) |
| w | NUMERIC(8,5) | NOT NULL | Box width (normalised) |
| h | NUMERIC(8,5) | NOT NULL | Box height (normalised) |
| track_id | BIGINT | NULL | Track ID for within-frame de-duplication |
| is_manual | SMALLINT | DEFAULT 0 | 0 automatic / 1 human-drawn |
| review_status | SMALLINT | DEFAULT 0 | 0 pending / 1 confirmed / 2 modified / 3 rejected |
| version_no | INT | DEFAULT 1 | Result version |
| hard_flag | SMALLINT | DEFAULT 0 | Hard example |
| hard_reason | VARCHAR(32) | NULL | low_conf / modified / inconsistent |
| reviewed_by | BIGINT | FK→sys_user, NULL | Reviewer |
| reviewed_at | TIMESTAMP | NULL | Reviewed at |
| created_at | TIMESTAMP | DEFAULT now() | Created |

#### 4.2.6 species_dict

**Table 4-7 species_dict**

| Field | Type | Constraint / default | Note |
|---|---|---|---|
| species_id | BIGINT | PK, AUTO_INCREMENT | Primary key |
| class_code | VARCHAR(32) | UNIQUE, NOT NULL | Class code, must match model labels exactly and in order |
| cn_name | VARCHAR(32) | NOT NULL | Chinese name |
| latin_name | VARCHAR(64) | NULL | Latin name |
| category | SMALLINT | NOT NULL | 1 commercial / 2 predator / 3 environmental |
| conf_thr | NUMERIC(4,2) | DEFAULT 0.50 | Per-class confidence threshold |
| in_stat | SMALLINT | DEFAULT 1 | Counted in statistics |
| status | SMALLINT | DEFAULT 1 | 1 enabled / 0 disabled |
| remark | VARCHAR(255) | NULL | Appearance and harm |
| created_at | TIMESTAMP | DEFAULT now() | Created |

#### 4.2.7 model_version

**Table 4-8 model_version**

| Field | Type | Constraint / default | Note |
|---|---|---|---|
| model_id | BIGINT | PK, AUTO_INCREMENT | Primary key |
| version_name | VARCHAR(64) | UNIQUE, NOT NULL | Version name, e.g. v8n-E3-001 |
| weight_path | VARCHAR(512) | NOT NULL | Path to the .pt weights |
| onnx_path | VARCHAR(512) | NULL | Path to the ONNX export |
| labels_path | VARCHAR(512) | NOT NULL | Path to the class-order file |
| dataset_ref | VARCHAR(128) | NULL | Dataset snapshot ID |
| map50 | NUMERIC(5,4) | NULL | mAP@0.5 |
| map50_95 | NUMERIC(5,4) | NULL | mAP@0.5:0.95 |
| recall_avg | NUMERIC(5,4) | NULL | Mean recall |
| fps | NUMERIC(6,2) | NULL | Inference frame rate |
| params_m | NUMERIC(6,2) | NULL | Parameters (millions) |
| status | SMALLINT | DEFAULT 0 | 0 candidate / 1 live / 2 retired |
| is_online | SMALLINT | DEFAULT 0 | Currently live |
| created_at | TIMESTAMP | DEFAULT now() | Registered at |

#### 4.2.8 train_experiment

**Table 4-9 train_experiment**

| Field | Type | Constraint / default | Note |
|---|---|---|---|
| exp_id | BIGINT | PK, AUTO_INCREMENT | Primary key |
| exp_name | VARCHAR(64) | NOT NULL | Experiment name, e.g. E3 |
| model_version_id | BIGINT | FK→model_version, NULL | Model produced |
| dataset_snapshot | VARCHAR(128) | NOT NULL | Dataset snapshot ID |
| split_ratio | VARCHAR(16) | NOT NULL | e.g. 7:2:1 |
| seed | INT | NOT NULL | Random seed |
| epochs | INT | NOT NULL | Epochs |
| batch_size | INT | NOT NULL | Batch size |
| lr | NUMERIC(8,6) | NOT NULL | Initial learning rate |
| augment_json | TEXT | NULL | Augmentation configuration |
| map50 | NUMERIC(5,4) | NULL | mAP@0.5 |
| map50_95 | NUMERIC(5,4) | NULL | mAP@0.5:0.95 |
| recall_avg | NUMERIC(5,4) | NULL | Mean recall |
| fps | NUMERIC(6,2) | NULL | Inference frame rate |
| params_m | NUMERIC(6,2) | NULL | Parameters (millions) |
| is_baseline | SMALLINT | DEFAULT 0 | Baseline run |
| note | VARCHAR(255) | NULL | What was changed |
| created_at | TIMESTAMP | DEFAULT now() | Recorded at |

#### 4.2.9 sys_message

**Table 4-10 sys_message**

| Field | Type | Constraint / default | Note |
|---|---|---|---|
| msg_id | BIGINT | PK, AUTO_INCREMENT | Primary key |
| msg_type | VARCHAR(32) | NOT NULL | capture_failed / task_failed / report_done |
| level | SMALLINT | DEFAULT 1 | 1 info / 2 warning / 3 critical |
| title | VARCHAR(128) | NOT NULL | Title |
| content | VARCHAR(512) | NULL | Body |
| target_role | VARCHAR(16) | NULL | Target role; null means everyone |
| ref_type | VARCHAR(32) | NULL | Related object type |
| ref_id | VARCHAR(64) | NULL | Related object ID |
| is_read | SMALLINT | DEFAULT 0 | 0 unread / 1 read |
| created_at | TIMESTAMP | DEFAULT now() | Created |

### 4.3 Volume and lifecycle estimates

**Table 4-11 Volume and lifecycle**

| Object | Initial size | Growth | Retention |
|---|---|---|---|
| Users and log | About 50 accounts, 10 000 log rows | About 300 rows per day | Accounts kept indefinitely; log online 180 days then archived |
| Sites and devices | About 20 sites | Slow, with the teaching data | Kept indefinitely |
| Image assets | About 1800 frames per session (250-400 KB each) ≈ 0.6 GB | 8-12 GB over 8 weeks | Originals kept indefinitely; intermediate files 7 days |
| Jobs and detected objects | About 2000 jobs, 500 000 objects | About 20 jobs and 5000 objects per day | Results online 1 year, archived monthly |
| Models and datasets | About 10 model versions, 20 dataset versions | 1-2 versions every two weeks | Weights kept indefinitely; training logs 90 days |
| Annotation records | About 30 000 records | About 2000 per day | Kept with the dataset version |
| Alert records | About 500 | 1-5 per day | Online 1 year, archived with the report |

## 5 Interface and interaction requirements

### 5.1 Style and layout

The interface uses a marine palette: deep-sea blue as primary (#0B4F6C) and teal as accent (#01BAEF) on white with light-grey cards. Detection classes keep fixed colours — sea cucumber orange, urchin purple, scallop pink, starfish yellow. The three states "unrecognised", "pending review" and "low confidence" are distinguished by dashed outlines, corner tags and translucent fill, never by colour alone. The layout is three-part: a top bar with the system mark, current user and messages; a left menu grouped and collapsible by business domain; a content area using card containers, one table style and one pagination control. The annotation and review bench is immersive: canvas centred, toolbar floating, wheel to zoom and drag to pan. Statistical pages are mostly ECharts, with chart colours matching the class colours.

Interaction rules: every list page offers keyword search, filters and paging; every slow operation (capture, detection, export, training) shows progress and can run in the background; every destructive action (delete, cancel, rollback, restore) asks for confirmation; form errors appear next to the field with the field highlighted; empty states give guidance and an entry point.

### 5.2 Page list

**Table 5-1 Page list**

| ID | Page | Type | Purpose | Requirements |
|---|---|---|---|---|
| P-01 | Sign-in | Form | Account and password, CAPTCHA, password recovery. | FR-M1-01 |
| P-02 | Running overview | Portal | Frames captured today, items to review, recent jobs and messages. | FR-M5-01, FR-M8-02 |
| P-03 | Capture control | Composite | Trigger capture, batch list, frame intake progress and failure reasons. | FR-M2-02 |
| P-04 | Image browser | List | Thumbnail grid with quality scores and filters; start detection on a selection. | FR-M2-04, FR-M2-03 |
| P-05 | Detection jobs | List | Job state, progress, queue position, cancel and retry. | FR-M3-02 |
| P-06 | Result detail | Detail | Overlay image, target list, per-class counts, export. | FR-M3-01, FR-M3-04, FR-M3-05 |
| P-07 | Manual review | Workspace | Add, delete and edit boxes on the canvas, compare versions, submit and roll back. | FR-M4-01, FR-M4-02 |
| P-08 | Hard samples | List | Filter by origin, inspect and remove. | FR-M4-03 |
| P-09 | Data export | Form | Sample range, split ratio, seed, and the snapshot record. | FR-M4-04 |
| P-10 | Statistics | Dashboard | Species composition, site heat map, trend curves, basis switching. | FR-M5-01, FR-M5-02, FR-M5-03 |
| P-11 | Inspection reports | Report | Period, template preview, generation and history. | FR-M5-04 |
| P-12 | Model experiments | Composite | Version list, experiment comparison, activation and rollback, dictionary and thresholds. | FR-M6-01, FR-M6-02, FR-M6-03, FR-M6-04 |
| P-13 | System settings | Management | Accounts, parameters, runtime monitoring, log and messages. | FR-M1-03, FR-M1-04, FR-M7-01, FR-M8-01, FR-M8-02 |

### 5.3 Key interaction flows

**Flow 1 — the main capture and detect chain.** Press start on the capture page → grab and score → register the passing frame with a resource code → start detection automatically or by hand → the result page shows the overlay and counts → low-confidence results enter the review queue → after review the statistics and reports update.

**Flow 2 — review and feedback.** Open the review queue → add, delete and edit boxes and classes → submit, creating a version and updating counts → corrected frames enter the hard-example pool → export a dataset for a sample range → record the dataset version for training.

**Flow 3 — training and deployment.** The algorithm engineer registers an experiment against a dataset version → training finishes and metrics are entered → the system compares against the baseline → if the metrics pass, the version is registered as a candidate → activation is recorded → later jobs use it automatically.

**Flow 4 — exception handling.** When a quality score falls below the threshold, the camera is unavailable or a job fails, the system raises a message → the collector or administrator reads the suggested remedy → adjust parameters or retake → the outcome is recorded, closing the loop.

**Flow 5 — side-by-side comparison, for demonstration.** The same frame is sent to the baseline and the improved model → rendered side by side → differences outlined → both models' mAP, FPS and per-frame time shown on one screen.

**Flow 6 — quality rejection, for demonstration.** A frosted sheet is slid in and the frame clouds → the score drops below 60 → it is marked for retake and kept out of the queue → the sheet is removed and the frame retaken → the score recovers and detection proceeds.

## 6 Non-functional requirements

### 6.1 Performance

**Table 6-1 Performance requirements**

| ID | Aspect | Requirement | Verification |
|---|---|---|---|
| NFR-P-01 | Response time | Routine queries and lists within 2 s (P90); complex statistics and reports within 5 s (P90). | Load test, P90 taken |
| NFR-P-02 | Detection speed | One 1920×1080 image end to end within 1.5 s on GPU and 5 s on CPU; batch average below 0.5 s per image on GPU. | Batch timing |
| NFR-P-03 | Capture | Video detection averages at least 15 FPS on GPU; a single frame end to end within 1.5 s; continuous capture at least 1 frame/s. | Streaming timing and latency |
| NFR-P-04 | Concurrency | At least 50 signed-in users online; 10 concurrent core users averaging under 3 s with at least 99 % success; at most 10 concurrent detection jobs. | Concurrency script |
| NFR-P-05 | Capacity | Designed for 100 000 image assets and 5 000 000 detected objects; paged and filtered queries on large tables within 3 s. | Synthetic data and timing |
| NFR-P-06 | Accuracy | Defined once in Table 3-43 of 3.5.4 and not repeated here. | Fixed test set and manual reading |
| NFR-P-07 | Continuous capture | At least 500 frames per run, processed asynchronously with progress; a failed file does not stop the run. | Intake test |
| NFR-P-08 | Resources | Application memory under 2 GB; GPU memory under 8 GB; CPU under 70 % at 50 % load. | Deployment monitoring |

### 6.2 Security and permissions

**Table 6-2 Security and permission requirements**

| ID | Aspect | Requirement | Verification |
|---|---|---|---|
| NFR-S-01 | Authentication | Every endpoint requires a valid JWT; tokens last 8 h and are not refreshed; passwords stored salted and hashed. | Security test and database check |
| NFR-S-02 | Authorisation | Roles enforced on the server; algorithm and configuration endpoints restricted; unauthorised access returns 403 and is logged. | Privilege-escalation cases |
| NFR-S-03 | File safety | Captured frames validated for format and size; filenames assigned by the server; storage not traversable over the web. | Malformed-frame injection |
| NFR-S-04 | Audit | Key actions (delete, review, activation, parameter change) leave tamper-proof traces searchable by person, time and object. | Audit sampling |
| NFR-S-05 | Session safety | Changing a password invalidates issued tokens; five consecutive failures lock the account for 15 minutes. | Session test |

### 6.3 Availability and reliability

**Table 6-3 Availability and reliability requirements**

| ID | Aspect | Requirement | Verification |
|---|---|---|---|
| NFR-U-01 | Usability | The core path (capture → detect → view) is completable in 5 minutes untrained; results offer both image and table views. | Walkthrough |
| NFR-U-02 | Job reliability | Detection job failure rate below 1 %; a failed job keeps its state and retries in one click; a cancel takes effect within 5 s. | Fault scenarios |
| NFR-U-03 | Data consistency | Review results, dashboard and exports agree; completed count matches image count; every result traces to its job and model version. | Consistency check |
| NFR-U-04 | Degradation | Without a GPU the system falls back to CPU with a notice; unfinished jobs resume or are marked for retry after a queue restart; no half-written results. | Fault injection |
| NFR-U-05 | Backup | Daily database backup, seven copies kept; one successful restore drill. | Restore drill |
| NFR-U-06 | Capture memory | Memory growth below 10 % over an 8-hour capture run. | 8-hour soak test, memory and frame curves |
| NFR-U-07 | Frame loss | Frame loss below 1 % over a continuous run. | 8-hour soak test |
| NFR-U-08 | Exposure stability | Mean brightness between frames varies by less than 10 % once locked. | Logged samples |
| NFR-U-09 | Single-frame latency | End to end within 1.5 s per frame. | 100 timings, median and P90 |

### 6.4 Maintainability and extensibility

**Table 6-4 Maintainability and extensibility requirements**

| ID | Aspect | Requirement | Verification |
|---|---|---|---|
| NFR-M-01 | Code standards | Backend follows PEP 8 with layered modules (router / service / data access); key algorithm and business logic unit-tested, core coverage at least 60 %. | Review and coverage report |
| NFR-M-02 | Model replaceability | Models plug in as versioned artefacts; switching or adding a version changes no business code; the inference engine is configurable. | Model switching demo |
| NFR-M-03 | Externalised configuration | Thresholds, concurrency and retention are configurable outside the code and change without a restart, except for key items. | Configuration change |
| NFR-M-04 | API standards | RESTful throughout with OpenAPI documentation and uniform error codes. | API review |
| NFR-M-05 | Extensibility | Interface layers reserved for multi-source capture, edge deployment and external control, extendable without touching the core data model. | Architecture review |

### 6.5 Deployment, compatibility and documentation

**Table 6-5 Deployment, compatibility and documentation requirements**

| ID | Aspect | Requirement | Verification |
|---|---|---|---|
| NFR-D-01 | Deployment | One-command deployment (Docker Compose or a script) completing within half a day on a clean Linux server. | Deployment drill |
| NFR-D-02 | Compatibility | Runs on Windows 10 for development and Linux in service; supports the last two major versions of Chrome and Edge plus 375 px browsing. | Compatibility test |
| NFR-D-03 | Documentation | Delivers the SRS, prototype notes, database design, high-level design, deployment manual, API documentation and user manual. | Document completeness check |
| NFR-D-04 | Seed data | A seed script pre-populates accounts, sites, the species dictionary, demonstration images and one trained model, so the system demonstrates out of the box. | Seed script run |

### 6.6 Privacy and compliance

**Table 6-6 Privacy and compliance requirements**

| ID | Aspect | Requirement | Verification |
|---|---|---|---|
| NFR-C-01 | Personal data | Phone numbers masked on display; user data used only for teaching; disabled accounts keep data but cannot sign in. | UI check and sampling |
| NFR-C-02 | Data provenance | Training and test data come only from public datasets and teaching footage, with the source shown on pages; no classified waters or real fishery locations. | Provenance review |
| NFR-C-03 | Image use | Demonstration images are for teaching only; exports carry no sensitive external information; shared screenshots need the supervisor's approval. | Usage check |

## 7 Plan and milestones

### 7.1 Phases and exit criteria

**Table 7-1 Training phases and exit criteria**

| Phase | Goal | Main tasks | Deliverables | Exit criteria |
|---|---|---|---|---|
| Requirements | Fix what the system does and what the algorithm detects | Business research and underwater scenario analysis; roles and use cases; write the SRS; review and freeze the baseline | SRS, review record | The SRS passes the supervisor's review with a signed baseline; requirement IDs are continuous and each has acceptance points and a trace |
| Prototyping | Prove the requirements are buildable and the interface acceptable | Information architecture and functional structure; high-fidelity core pages; walkthrough and feedback; revise prototype and requirements | Structure chart, page prototypes, interaction notes, review minutes | The core loop (capture → detect → review → statistics) is clickable; every walkthrough comment is closed; prototypes map one-to-one to SRS items |
| Database design | Settle the data model | Conceptual (ER) design; logical model and tables; schema script and index strategy; seed data | ER diagram, data dictionary, SQL script, seed script | The ER diagram covers every core entity; every table has a key and the necessary constraints; the script runs on a clean instance in one pass |
| Algorithm baseline and improvement | Get the YOLOv8 baseline running and improve it | Dataset acquisition and preprocessing; baseline training and evaluation; enhancement and model experiments; metric comparison | Baseline report, improvement notes, weights and evaluation report | Baseline mAP@0.5 at least 0.70; the improved model shows an explainable gain and the runs reproduce |
| Coding | Implement every functional requirement | Backend endpoints; frontend pages; algorithm service and queue integration; unit tests | Source code, API documentation, unit test report | Every high-priority item in Table 3-1 is implemented and self-tested; documentation matches the implementation |
| Integration testing | Verify the requirements are met | Test case design and execution; performance and accuracy tests; defect fixing and regression; traceability check | Test plan, cases, defect report, summary | 100 % of cases executed, critical defects at zero, at most five minor defects left with a plan |
| Deployment and acceptance | Deliver a demonstrable system | Deployment drill and seed data; acceptance testing; closing materials and defence | Deployment manual, acceptance report, user manual, defence material | Every acceptance item passes; the demonstration runs unbroken; documents are complete |

### 7.2 Eight-week schedule

**Table 7-2 Eight-week schedule**

| Week | Phase | Tasks | Output | Owner |
|---|---|---|---|---|
| Week 10 (from 11-02) | Requirements | Form the team and divide work; business research; fix classes and metric definitions; build the document skeleton | Research notes, division table, SRS skeleton | All / Yao Tianyu |
| Week 11 (from 11-09) | Requirements / prototype start | Complete chapters 1-6 of the SRS and freeze the baseline at review; start information architecture and core prototypes | SRS V1.0, information architecture | Yao Tianyu / Sun Jianheng |
| Week 12 (from 11-16) | Prototype / database / algorithm start | High-fidelity core pages and walkthrough; ER diagram and schema script; acquire DUO and preprocess (7782 images, official test set 1111) | Prototypes, ER diagram, schema script, dataset inventory | Sun Jianheng / Gao Tianxiang |
| Week 13 (from 11-23) | Algorithm baseline and improvement | Baseline training and evaluation; underwater enhancement (colour correction, dehazing) and model experiments; metric records | Weights and evaluation reports for baseline and improved models | Gao Tianxiang |
| Week 14 (from 11-30) | Coding | Backend modules for users, images and jobs; inference service and the in-process job pool; frontend sign-in, image and job pages | Endpoint code, frontend pages, API documentation | Gao Tianxiang / Sun Jianheng |
| Week 15 (from 12-07) | Coding | Review, dashboard, annotation bench and model management pages; the feedback loop joined end to end | Remaining code, integration self-test | Gao Tianxiang / Sun Jianheng |
| Week 16 (from 12-14) | Integration testing | Functional and performance cases; accuracy acceptance; defect fixing and regression; traceability check | Test cases, defect report, summary | Fu Yijia / all |
| Week 17 (from 12-21) | Deployment and acceptance | Deployment drill and seed data; acceptance testing and closing materials; defence rehearsal | Deployment manual, acceptance report, defence material | All / Yao Tianyu |

Every document in this repository is Markdown, and the inspection report the system produces is
Markdown too. The Word, PDF and Excel formats in the table above describe what may be handed to the
supervisor; nothing is converted unless it is asked for, and the Markdown is the copy that is kept.

### 7.3 Deliverables

**Table 7-3 Project deliverables**

| Phase | Deliverable | Format | Owner | Acceptance |
|---|---|---|---|---|
| Requirements | SRS (this document) | Word / PDF | Requirements group | Supervisor review |
| Requirements | Review record and baseline confirmation | Word | Project lead | Signed at the review |
| Prototyping | Structure chart and page prototypes | HTML / images | Prototype group | Walkthrough demo |
| Prototyping | Interaction notes | Word | Prototype group | Walkthrough review |
| Database design | ER diagram and data dictionary | PDF / Word | Database group | Design review |
| Database design | Schema and seed scripts | SQL | Database group | Runs on a clean instance |
| Algorithm | Baseline and improved weights | .pt / .onnx | Algorithm group | Evaluated on the fixed test set |
| Algorithm | Experiment and evaluation report | Word | Algorithm group | Metric review |
| Coding | Source code | Git repository | Development group | Review and build |
| Coding | API documentation | OpenAPI / Word | Backend group | Joint debugging check |
| Testing | Test plan and cases | Word / Excel | Test group | Review |
| Testing | Defect report and test summary | Word / Excel | Test group | Regression |
| Deployment | Deployment and user manuals | Word | Operations | Deployment drill |
| Deployment | Acceptance report and defence material | Word / PPT | Project lead | Closing review |

### 7.4 Roles

**Table 7-4 Team roles and responsibilities**

| Member | Role | Primary responsibility | Secondary and backup | Key deliverables |
|---|---|---|---|---|
| Yao Tianyu | Group lead / capture owner | USB camera capture (the microcontroller is optional), project management and schedule, author of the SRS, defence speaker | Deployment and integration | SRS, weekly reports, defence material |
| Gao Tianxiang | Algorithm and backend owner | YOLOv8 baseline training and improvement experiments, inference service packaging, core business endpoints and database design | Model activation and rollback | Both sets of weights and the ablation report, API documentation, schema script |
| Sun Jianheng | Frontend and data engineering owner | 13 pages and visualisation, review canvas, annotation and dataset versions, automation scripts | Statistical reports | Frontend code, annotated datasets, export scripts |
| Fu Yijia | Quality and documentation owner | Review records and document versioning, test case design and execution, interface walkthroughs and acceptance records, ID and terminology consistency | Species dictionary upkeep | Test case set and report, review minutes, acceptance records |

## 8 Acceptance criteria

### 8.1 Acceptance items

**Table 8-1 Acceptance items and criteria**

| ID | Area | Item | Criterion | Method |
|---|---|---|---|---|
| AC-01 | Account | Sign-in and session | Five failures lock the account and show the remaining time; the password column is a hash; a correct password is refused while locked. | Functional test |
| AC-02 | Permission | Roles and permissions | A collector calling the activation endpoint gets 403 and the attempt is logged; an unauthenticated user cannot reach capture endpoints. | Privilege test |
| AC-03 | Account | Account management | A disabled account cannot sign in and its history stays searchable; duplicate phone numbers are refused. | Functional test |
| AC-04 | Audit | Operation log | A review traces to operator and before/after values; no endpoint deletes a log entry. | Functional test |
| AC-05 | Capture | Single-frame registration | With capture stopped there is no image source; a timestamp more than 5 s off is refused; a duplicate frame stores once. | Functional test |
| AC-06 | Capture | Scheduled capture | Ten minutes and six captures produce six batches; a failed capture marks the run failed. | Functional test |
| AC-07 | Capture | Quality scoring | A defocused frame scores below 60 and stays out of the queue; retake frames are marked. | Functional test |
| AC-08 | Capture | Batch search | Four filters combine correctly; a batch drills down to frames. | Functional test |
| AC-09 | Capture | Cleanup | After cleanup references are null and disk usage drops; originals survive by default. | Functional test |
| AC-10 | Detection | Immediate detection | Trigger to box within 3 s; an image not from capture is refused. | Performance and function |
| AC-11 | Detection | Batch and queue | A 100-frame job updates live; a cancel takes effect within 5 s; failed frames retry. | Functional test |
| AC-12 | Detection | Parameters | Changing a threshold changes the result count; job parameters cannot be edited afterwards. | Functional test |
| AC-13 | Detection | Results and counts | The count matches the number of rows; the class filter updates both together. | Functional test |
| AC-14 | Detection | Export | CSV rows equal page rows; Excel opens it with Chinese intact. | Functional test |
| AC-15 | Review | Review bench | Deleting a box lowers the count, drawing one raises it; the automatic result stays viewable. | Functional test |
| AC-16 | Review | Versions and rollback | Two reviews produce two versions; after rollback the result matches the target. | Functional test |
| AC-17 | Review | Hard-example set | Every corrected sample enters the pool with its origin; removed ones disappear. | Functional test |
| AC-18 | Review | Dataset export | One seed gives identical file lists; unreviewed samples are refused. | Reproducibility test |
| AC-19 | Statistics | Species composition | Switching the basis changes numbers and label together; shares total 100 %. | Data check |
| AC-20 | Statistics | Site distribution | Heat map and ranking agree; an empty state appears with no data. | Functional test |
| AC-21 | Statistics | Trend comparison | Rates reconcile by hand; a missing baseline shows a dash. | Functional test |
| AC-22 | Statistics | Inspection report | Report figures match the dashboard; the footer carries version and basis. | Data check |
| AC-23 | Model | Version registration | Missing metrics refused; a version name always has exactly one row - registering it again updates that row. | Functional test |
| AC-24 | Model | Activation and rollback | New jobs use the new version after activation; the version number matches after rollback. | Functional test |
| AC-25 | Model | Experiments | Baseline and improved runs compare in one table; two identical runs differ by less than 1 %. | Reproducibility test |
| AC-26 | Model | Species dictionary | A class code that does not match labels is refused; a new threshold applies to new jobs. | Functional test |
| AC-27 | System | Parameters | A new concurrency limit constrains new jobs; changes show before and after values. | Functional test |
| AC-28 | System | Runtime monitoring | Queue length visibly rises under a large batch; disk usage past its threshold turns red. | Functional test |
| AC-29 | System | Messages | An offline event creates one unread message; repeats within an hour add nothing. | Functional test |
| AC-30 | Algorithm | Overall accuracy | mAP@0.5 ≥ 0.75 and mAP@0.5:0.95 ≥ 0.45 on the fixed test set. | Fixed-set evaluation |
| AC-31 | Algorithm | Per-class accuracy | Recall ≥ 0.75 and precision ≥ 0.70 for all four classes. | Fixed-set evaluation |
| AC-32 | Algorithm | Improvement | The improved model gains at least 0.03 mAP@0.5 and keeps at least 90 % of baseline FPS. | Same-condition comparison |
| AC-33 | Algorithm | Counting accuracy | De-duplicated counts deviate from manual reading by at most 15 %. | Manual comparison |
| AC-34 | Performance | End to end and service | Single frame end to end within 1.5 s on GPU; list endpoints P90 within 2 s. | Timing and load test |
| AC-35 | Delivery | Documents and traceability | The matrix covers all 29 requirements, each with an acceptance item; process documents complete. | Document review |
| AC-36 | Process | Demonstration completeness | The full chain from capture trigger to report export runs live without interruption; the model iteration loop can be described and its key steps shown. | Live demonstration |

### 8.2 Acceptance deliverables

At closing, submit: ① a runnable environment with seed data; ② this document and its review record; ③ prototypes, database design, high-level design and API documentation; ④ baseline and improved weights with evaluation reports; ⑤ test plan, cases, defect report and summary; ⑥ deployment and user manuals; ⑦ the acceptance report and defence material. Everything is archived in the Git repository, with key checkpoints submitted to the supervisor.

### 8.3 Defects and known issues

Defects found in acceptance testing are handled by severity. Critical (system unusable, data loss, accuracy below target) and major (core path blocked, permissions broken) must reach zero before acceptance. Minor defects (non-core pages, wording, experience) may number at most five, each entered in a known-issues list with impact and a plan, confirmed by the supervisor and archived with the closing material. If accuracy falls short, an improvement record and a plan are required; lowering the threshold to pass acceptance is not allowed.

## 9 Risks

**Table 9-1 Risk register**

| ID | Risk | Likelihood | Impact | Response | Owner |
|---|---|---|---|---|---|
| R-01 | Scope too large to close both the business and algorithm loops in 8 weeks | High | High | Trim by MoSCoW at the week-2 review, protecting the two chains capture-detect-review-statistics and hard-example-train-deploy; side-by-side comparison and shaded rollout are droppable; track completion weekly. | Project lead |
| R-02 | Insufficient or poorly labelled underwater data, missing the accuracy target | High | High | Use DUO to guarantee baseline accuracy; DUO and URPC overlap and must never be mixed, or near-duplicate frames across the split inflate the metric; baseline evaluation in week 4; improvements only add; double-check annotations on at least 10 % of samples; pre-labelling cuts cost. | Algorithm group |
| R-03 | Poor image quality (turbidity, colour cast, small targets) raising misses and false positives | High | Medium | Correct colour and dehaze on the data side with a comparative experiment; send every low-confidence result to human review so outward results stay trustworthy; compare counts against manual reading. | Algorithm group |
| R-04 | Insufficient GPU capacity, queueing slowing training and inference | Medium | High | Schedule training windows with one job at a time; keep models at yolov8n or yolov8s; prepare a CPU fallback and ONNX acceleration. | Operations / algorithm |
| R-05 | Cross-frame double counting making statistics untrustworthy | Medium | High | De-duplicate by track ID within a time window, with a switch; acceptance compares deviation against manual counting; the de-duplication logic has its own unit test. | Algorithm group |
| R-06 | Continuous capture and batch jobs blocking or timing out the service | Medium | Medium | Asynchronous queues for capture and detection; frontend polling; batch size and concurrency configured externally; a capacity load test in week 7. | Backend group |
| R-07 | Joint debugging of frontend, backend and algorithm slipping | Medium | Medium | Freeze the API contract (OpenAPI) in week 5; debug against mock weights first; raise blockers at the daily stand-up. | Development group |
| R-08 | Model versions and class mappings drifting, making results untraceable | Medium | Medium | Freeze model version and parameters at job creation and store them with results; validate the class mapping before activation; log every activation and retirement. | Algorithm / backend |
| R-09 | Uneven skills causing an unbalanced division of work | Medium | Medium | Assign by skill profile with technical research in W2; name a primary and backup for each key module; weekly code walkthroughs to spread knowledge. | Project lead |
| R-10 | Environment differences breaking the acceptance demo | Low | High | Rehearse fully in the target environment in W8; provide Docker Compose and the seed script; keep an offline installer as backup. | Operations |
| R-11 | Public dataset unavailable or missing classes, blocking training | Medium | High | Secure the dataset and record its statistics before week 12; keep UTDAC or a Roboflow repackaging as alternates; if still unavailable, cut to two classes (sea cucumber, sea urchin) and amend 3.5 and 8.1 together. | Gao Tianxiang |

## Appendix A Traceability matrix

**Table A-1 Traceability matrix**

| Requirement | Module | Priority | Use cases | Acceptance |
|---|---|---|---|---|
| FR-M1-01 | M1 | P0 | UC-01 | AC-01 |
| FR-M1-02 | M1 | P0 | UC-09 | AC-02 |
| FR-M1-03 | M1 | P1 | UC-09 | AC-03 |
| FR-M1-04 | M1 | P1 | UC-05 | AC-04 |
| FR-M2-01 | M2 | P0 | UC-01 | AC-05 |
| FR-M2-02 | M2 | P1 | UC-02 | AC-06 |
| FR-M2-03 | M2 | P0 | UC-01, UC-03 | AC-07 |
| FR-M2-04 | M2 | P1 | UC-02 | AC-08 |
| FR-M2-05 | M2 | P2 | UC-02 | AC-09 |
| FR-M3-01 | M3 | P0 | UC-03 | AC-10 |
| FR-M3-02 | M3 | P0 | UC-04 | AC-11 |
| FR-M3-03 | M3 | P1 | UC-03, UC-04 | AC-12 |
| FR-M3-04 | M3 | P0 | UC-03 | AC-13 |
| FR-M3-05 | M3 | P1 | UC-03 | AC-14 |
| FR-M4-01 | M4 | P0 | UC-05 | AC-15 |
| FR-M4-02 | M4 | P1 | UC-05 | AC-16 |
| FR-M4-03 | M4 | P1 | UC-05 | AC-17 |
| FR-M4-04 | M4 | P1 | UC-06 | AC-18 |
| FR-M5-01 | M5 | P1 | UC-08 | AC-19 |
| FR-M5-02 | M5 | P1 | UC-08 | AC-20 |
| FR-M5-03 | M5 | P2 | UC-08 | AC-21 |
| FR-M5-04 | M5 | P1 | UC-08 | AC-22 |
| FR-M6-01 | M6 | P0 | UC-07 | AC-23 |
| FR-M6-02 | M6 | P1 | UC-07 | AC-24 |
| FR-M6-03 | M6 | P0 | UC-06 | AC-25 |
| FR-M6-04 | M6 | P0 | UC-07 | AC-26 |
| FR-M7-01 | M7 | P1 | UC-09 | AC-27 |
| FR-M8-01 | M8 | P1 | UC-04 | AC-28 |
| FR-M8-02 | M8 | P2 | UC-09 | AC-29 |

## Appendix B Change record

**Table B-1 Change record**

| Version | Date | Raised by | Change | Reason | Approved by |
|---|---|---|---|---|---|
| V0.1 | 2026-10-28 | Requirements group | Business research recorded; document skeleton built; a first division into ten functional modules. | Requirements analysis starts and needs a baseline structure. | Supervisor |
| V0.9 | 2026-11-01 | Requirements / algorithm group | Detailed functional, data and non-functional requirements plus accuracy metrics; chapters 3-6 complete. | Verifiability must be checked before prototyping starts. | Supervisor |
| V1.0 | 2026-11-03 | Project lead | Review comments integrated; use cases, acceptance criteria, risks and the traceability matrix added; baseline established. | Forms the submission draft and the input for later phases. | Supervisor |
| V1.1 | 2026-11-03 | Yao Tianyu | Switched to direct capture from the local camera; capture-terminal modules and tables removed; 3.5 algorithm requirements and 2.4 architecture added; NFR numbering conflicts fixed; 2.3 scenarios, UC-01/UC-09 and 5.3 flows rewritten; wording inconsistent with the new architecture removed. | Implements the annotations on the final revision of 09. | Internal group review |
| V1.2 | 2026-11-03 | Yao Tianyu | Marine-debris class and per-class metrics added; capture hardware list added (trigger board, temperature and turbidity sensors, status display); environment reporting added to the capture interface; streaming wording, team size and baseline-freeze week corrected; dataset size and acquisition risk added. | Implements the capture plan change and settles the requirements baseline. | Internal group review |
| V1.3 | 2026-11-04 | Yao Tianyu | Marine-debris class removed and four classes restored; dataset wording unified to DUO; AL-08 and AL-09 deleted from the metric table and AL-03 limited to per-class recall; scenery list in Table 2-3 and class palette in 5.1 adjusted. | No public labels exist for that class and in-house data cannot support an independent accuracy metric; focus on four commercial and predator species to keep the metric basis consistent. | Internal group review |
| V1.12 | 2026-11-11 | Yao Tianyu | The table count moves from thirteen to fourteen. §4.1 gains `detect_task_item`, which records the frames assigned to each detection task when it is created: one row per frame, with its own state and box count. | A task's work list was a query re-evaluated by every worker, so two workers could claim the same frames and a frame with no objects never finished; the decision is recorded in ADR 12. | Internal group review |
| V1.13 | 2026-11-12 | Gao Tianxiang | AC-23 states what version registration does instead of a refusal it never implemented: a version name always has exactly one row, and registering an existing name updates that row. | The registration script has been idempotent since P2-06c and `scripts/init_db.py` registers the delivered version on every run, so a refused duplicate would make a fresh install non-repeatable - the outcome AC-23 wants, one row per name, was already held. | Internal group review |
| V1.11 | 2026-11-10 | Yao Tianyu | The thirteen page names in §5.2 are one scheme now: object plus action, four characters where the language allows, no `page` suffix, no conjunction. The old set mixed grammars (`capture control` beside `image browsing`), reused `workbench` as both a page and a modifier, and disagreed with `docs/traceability-en.md` on nine of thirteen names in English. | A menu is scanned, not read: parallel entries are quicker to find, and three spellings of one page is three chances to edit the wrong file. | Internal group review |
| V1.10 | 2026-11-07 | Yao Tianyu | The technology table no longer claims Celery and Redis: batch jobs run in a fixed thread pool inside the one FastAPI process, as ADR 03 decided. SQLAlchemy 2.0 corrected to 2.1, the version pinned in requirements. | The SRS still advertised a message broker the architecture had already rejected, and a reader comparing the two documents would have believed the system had a component it does not. | Internal group review |
| V1.9 | 2026-11-07 | Yao Tianyu | Table 2-3 gains a status display and two status LEDs; the MCU row adds driving the display. Everything shown on the screen is English or numeric. | The screen and LEDs come from the STM32 kit already on hand, so they cost nothing; V1.4 removed the display on minimum-cost grounds and that premise no longer holds. The screen shows device state only — business data stays on the web side. | Internal group review |
| V1.8 | 2026-11-07 | Yao Tianyu | Table 2-3 returns to the existing LED desk lamp; the strip, MOSFET and separate supply from V1.7 are withdrawn, and the MCU row goes back to trigger and turbidity. | The lamp on hand is USB-powered (DC), 4000 K, 10 W and advertised as flicker-free, so the flicker argument that justified the strip does not apply. ADR 09 is superseded by ADR 10. | Internal group review |
| V1.7 | 2026-11-07 | Yao Tianyu | Table 2-3 replaces the desk lamp with a 12 V LED board, an IRF520 MOSFET module and its own supply, and the MCU row gains PWM dimming. | Both the architecture diagram and the parts list said the MCU controls the fill light, but a mains desk lamp cannot be controlled by a program — the claim was empty. A fixed board also removes the variation between capture sessions (ADR 09). | Internal group review |
| V1.6 | 2026-11-06 | Yao Tianyu | The inspection report is produced as Markdown; scenario 5, FR-M5-04 and §7 say so, and §7 records that the Word, PDF and Excel formats are conversion targets only. | Every document in the repository is Markdown and none of them is submitted as a converted file; keeping two formats would mean keeping two copies, one of which is always stale. | Internal group review |
| V1.5 | 2026-11-06 | Yao Tianyu | Four tables added to §4.1: `dataset`, `dataset_item`, `report`, `sys_param`; the nine-table decision of V1.1 revised with the reason recorded in ADR 08. | Building the skeleton showed three requirements had no storage: a snapshot exported before any experiment, a report history filtered by period and basis, and parameter changes that must persist and stay audited. | Internal group review |
| V1.4 | 2026-11-05 | Yao Tianyu | Water-temperature field, probe and status display removed; turbidity changed from NTU to a 0-100 relative value and renamed turbidity_rel; Table 2-3 updated to the selected parts (desk lamp, ultra-clear glass tank, real seafood targets, ME2100A-IIC). Correction of 11-05: the tank material in 2.6 changed from acrylic to ultra-clear glass to match Table 2-3. | Purchase plan settled: meet capture and cleanliness needs at minimum cost, keeping turbidity as the only sensor. | Internal group review |

## Appendix C Terminology consistency

This document shares one terminology with the prototype notes, database design and high-level design that follow. Species classes follow the species dictionary (`species_dict`). Requirement IDs `FR-M<module>-<index>` map one-to-one to Table 3-1. Use cases `UC-XX` map to section 3.4. Acceptance items `AC-XX` map to chapter 8. Table names use lowercase with underscores, and the field dictionary is section 4.2. Throughout, "detection" means YOLO-based object detection; "count" means individuals after cross-frame de-duplication; "live model" means the version currently used for new jobs. Where documents disagree, the V1.1 submission draft governs. Tables are numbered per chapter as "Table <chapter>-<index>", appendix tables as "Table <letter>-<index>"; placeholder forms such as "Table 3-x" are not used.
