# Kotha — Sylheti Speech Recognition Evaluation Report

**Evaluation Date:** 2026-11-24  
**Provider:** `openai_compatible`  
**Model:** `whisper-large-v3-turbo`  
**Total Audio Clips:** 16  
**Mean CER (Character Error Rate):** `57.90%`  
**Mean WER (Word Error Rate):** `82.87%`  
**Mean Latency:** `3060.7 ms` (Median: `1436.6 ms`)  

---

## 1. Scenario-Level Breakdown

| Scenario | Description / Domain | Count | Mean CER | Mean WER | Mean Latency |
|:---|:---|:---:|:---:|:---:|:---:|
| `A1` | Acute fever with chills (জ্বর ও কাঁপুনি) | 2 | 62.64% | 96.88% | 6815.7 ms |
| `A2` | Severe chest pain & breathlessness (বুক বেদনা ও শ্বাসকষ্ট) | 2 | 80.45% | 104.54% | 4219.4 ms |
| `A3` | Abdominal pain & vomiting (পেট কামড়ানি ও বমি ভাব) | 2 | 76.84% | 125.44% | 3251.0 ms |
| `B1` | Pediatric high fever & convulsions (বাচ্চার জ্বর ও খিঁচুনি) | 2 | 0.00% | 0.00% | 5114.1 ms |
| `B2` | Elderly dizziness & stroke signs (মাথা ঘুরা ও অজ্ঞান হওয়া) | 2 | 36.41% | 50.00% | 1895.1 ms |
| `B3` | Chronic joint/back pain (বাত বেদনা ও কোমর ব্যথা) | 1 | 86.42% | 150.00% | 999.8 ms |
| `C1` | Diarrhea & dehydration (পাতলা পায়খানা ও দুর্বলতা) | 3 | 51.26% | 66.67% | 1184.0 ms |
| `C2` | Severe skin infection/rash (চুলকানি ও ঘা) | 2 | 86.72% | 111.11% | 914.1 ms |

---

## 2. Per-Recording Results & Error Analysis

| ID | Scenario | File | Duration | CER | WER | Latency | Reviewer |
|:---|:---:|:---|:---:|:---:|:---:|:---:|:---:|
| `rec_001` | `A1` | `New Recording.wav` | 8.3s | 75.29% | 106.25% | 5440 ms | Fahim |
| `rec_002` | `A1` | `New Recording 2.wav` | 9.2s | 50.00% | 87.50% | 8192 ms | Noyon |
| `rec_003` | `A2` | `New Recording 3.wav` | 8.7s | 81.31% | 109.09% | 3110 ms | Fahim |
| `rec_004` | `A2` | `New Recording 4.wav` | 6.8s | 79.59% | 100.00% | 5329 ms | Fahim |
| `rec_005` | `A3` | `New Recording 5.wav` | 7.8s | 61.63% | 93.75% | 1369 ms | Fahim |
| `rec_006` | `A3` | `New Recording 6.wav` | 7.8s | 92.05% | 157.14% | 5134 ms | Noyon |
| `rec_007` | `B1` | `New Recording 7.wav` | 12.3s | 0.00% | 0.00% | 8724 ms | Noyon |
| `rec_008` | `B1` | `New Recording 8.wav` | 9.3s | 0.00% | 0.00% | 1505 ms | Fahim |
| `rec_009` | `B2` | `New Recording 9.wav` | 8.9s | 0.00% | 0.00% | 1006 ms | Noyon |
| `rec_010` | `B2` | `New Recording 10.wav` | 11.9s | 72.82% | 100.00% | 2784 ms | Noyon |
| `rec_011` | `B3` | `New Recording 11.wav` | 8.4s | 86.42% | 150.00% | 1000 ms | Fahim |
| `rec_012` | `C1` | `New Recording 12.wav` | 14.0s | 80.62% | 100.00% | 1229 ms | Noyon |
| `rec_013` | `C1` | `New Recording 13.m4a.wav` | 9.1s | 73.17% | 100.00% | 1109 ms | Fahim |
| `rec_014` | `C1` | `New Recording 14.m4a.wav` | 13.3s | 0.00% | 0.00% | 1213 ms | Noyon |
| `rec_015` | `C2` | `New Recording 15.m4a.wav` | 9.5s | 93.81% | 122.22% | 1167 ms | Noyon |
| `rec_016` | `C2` | `New Recording 16.m4a.wav` | 15.9s | 79.63% | 100.00% | 661 ms | Fahim |

---

## 3. Dialect Phonetic & Acoustic Observations

1. **Phonetic Shifts**: Standard Bangla aspirates (/ch/, /ph/) systematically spirantize to /s/ and /f/ in Sylheti (e.g., 'পানি' -> 'ফানি', 'ব্যথা' -> 'বেদনা', 'করছি না' -> 'করসিনা'). General-purpose Whisper models transcribe these variably depending on audio clarity.
2. **Lexical Divergence**: Regional verbs like 'লাগের', 'করার', 'বারর', 'অইজার' require downstream glossary mapping to prevent hallucination.
3. **Audio Quality**: Stereo 48kHz recordings exhibited zero clipping or distortion. Downsampling to 16kHz mono via FFmpeg preserved high speech intelligibility.