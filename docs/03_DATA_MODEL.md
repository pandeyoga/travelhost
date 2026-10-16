# 03 — DATA MODEL / ENTITY REGISTRY (SSOT)
## Travel & Fleet Management Ecosystem

> **Single Source of Truth** untuk koleksi MongoDB, field kunci, dan **invarian**.
> Sinkron dengan `scripts/verify_contract.py` (`CANONICAL_COLLECTIONS`) & `scripts/verify_data_integrity.py` (`CONCEPTS`).
> Tambah koleksi ⇒ update **dokumen ini + kedua script**. **Penamaan generik (tanpa brand).**

---

## 1. KOLEKSI KANONIK (25)
```
users, sessions,
vehicles, drivers, customers,
leads, lead_activities, conversations, messages,
bookings, trips, locations, trip_shares,
payments, expenses, invoices,
notification_tasks, broadcasts, maintenance_records,
destinations, articles, testimonials,
audit_logs, settings, user_onboarding
```

### Alias TERLARANG (drift) → kanonik
`cars/armada → vehicles` · `sopir → drivers` · `clients/pelanggan → customers` · `orders/pesanan → bookings` · `prospects → leads` · `chats → messages` · `gps/positions/tracking → locations` · `payment → payments` · `cost/biaya → expenses` · `bills/faktur → invoices` · `reminders → notification_tasks` · `maintenance → maintenance_records` · `blog/posts → articles` · `config → settings`.

---

## 2. SKEMA KUNCI (field penting saja)

### users
`id(usr_)`, `name`, `email`(unik), `password_hash`, `role`(owner|ops_admin|driver), `phone`, `status`(active|inactive), `created_at`
### sessions
`token`(sess_), `user_id`, `created_at`, `expires_at`
### vehicles
`id(veh_)`, `code`, `name`, `plate_number`, `type`, `capacity`(int), `status`(available|on_trip|maintenance), `kir_expiry`(ISO), `tax_expiry`(ISO), `last_service_date`, `next_service_date`, `odometer`, `features[]`, `photos[]`, `publish_to_web`(bool), `ownership`(owned|partner, E16), `partner_id`(ptn_, nullable, E16), `created_at`
  · **E8 (servis preventif)**: `service_interval_km`(num), `service_interval_days`(int), `last_service_odometer`(num) — dipakai `services/preventive.py` untuk status jatuh tempo (overdue|due_soon|ok) per basis km & waktu.
  · **P10/FASE 2 (web immersif)**: `gallery[]`({url,caption}), `tour_scenes[]`({id,label,panorama,thumbnail,links[]({nodeId,yaw,pitch})}), `specs[]`({key,label,value}), `highlights[]`, `year`(int), `color`, `price_from`(num)
### drivers
`id(drv_)`, `name`, `phone`, `sim_number`, `sim_expiry`(ISO), `status`(online|resting|offline), `current_vehicle_id`, `rating`(0-5), `created_at`; **E11 payroll:** `comp`{`base_salary_monthly`(num), `commission_per_trip`(num), `commission_pct_revenue`(num,%), `allowance_per_km`(num), `revenue_base`(trip|booking), `enable_base`/`enable_commission_trip`/`enable_commission_pct`/`enable_allowance_km`(bool)} — konfigurasi kompensasi per driver (embedded)
### customers
`id(cus_)`, `name`, `phone`, `phone_normalized`(+62, B4 dedupe key), `email`, `type`(individual|corporate), `city`, `address`, `total_trips`(int), `lifetime_value`(num), `notes`, `created_at`
### leads
`id(led_)`, `customer_name`, `phone`, `phone_normalized`(+62, B4), `email`, `source`(website|whatsapp|manual|ads), `stage`(new|contacted|quoted|negotiation|won|lost), `assigned_to`(user_id), `destination`, `trip_date`, `pax`(int), `message`, `quotation_amount`, `value`(num), `converted_customer_id`(cus_), `linked_customer_id`(cus_, B4 auto-link), `created_at`, `last_activity_at`
  · **E-ADS (atribusi)**: `channel`(google_ads|meta_ads|tiktok_ads|instagram|email|referral|website|organic|direct|…), `attribution`{`first_touch`,`last_touch`,`channel`} (tiap touch: utm_source/medium/campaign/term/content, gclid, fbclid, ttclid, referrer, landing_page, ts), `utm_source`, `utm_campaign`, `marketing_consent`(bool), `consent_at`(ISO|null). `channel` dipakai `analytics.channels_roi` (CPL/CAC/ROAS). Lead dari `lead-ads` webhook → `source=ads`, `channel={provider}_ads`, `marketing_consent=true`.
### lead_activities
`id(lac_)`, `lead_id`(led_), `user_id`(usr_, nullable), `type`(created|note|call|stage_change|assignment|converted), `text`, `from_stage`, `to_stage`, `created_at`
### conversations
`id(cnv_)`, `lead_id`|`customer_id`(nullable), `channel`(web|whatsapp|internal), `contact_name`, `contact_phone`, `subject`, `status`(open|snoozed|closed), `assigned_to`(usr_, nullable), `labels[]`, `unread`(int), `chat_token`(untuk widget publik), `last_message_at`, `last_message_preview`, `snooze_until`, `created_at`
### messages
`id(msg_)`, `conversation_id`(cnv_), `sender`(agent|customer|system), `author_id`(usr_, nullable), `body`, `internal`(bool, catatan internal), `status`(sent|delivered|read), `created_at`
### bookings
`id(bk_)`, `code`(BK-0001), `customer_id`, `vehicle_id`(nullable saat status=pending), `driver_id`, `origin`, `destination`, `start_datetime`(ISO), `end_datetime`(ISO), `base_price`(int-rupiah), `add_ons[]`({label,amount}), `total_amount`(int-rupiah), `paid_amount`(int-rupiah), `payment_status`(belum_bayar|dp|lunas|selesai), `status`(draft|pending|hold|confirmed|ongoing|completed|cancelled), `customer_name`(snapshot), `vehicle_name`(snapshot), `driver_name`(snapshot), `notes`, `created_at`, `departure_confirmed_at`(ISO, E3 — konfirmasi keberangkatan/WA); **E17:** `rescheduled_at`(ISO); **E18 DP-gate:** `require_dp`(bool, input), `hold_expires_at`(ISO), `hold_hours`(int), `dp_percent`(num), `dp_amount`(int-rupiah), `dp_met_at`(ISO), `hold_expired_at`(ISO); **E19 self-service:** `source`(website|null), `requested_vehicle_type`(str), `pax`(int), `approved_at`(ISO); **E20 rombongan:** `group_id`(prefix `grp_`), `group_size`(int), `group_index`(int, 1-based); **E21 pembatalan:** `cancellation_reason`(str), `cancellation_fee`(int-rupiah, denda ditahan sbg pendapatan), `refund_amount`(int-rupiah, dana dikembalikan), `cancelled_at`(ISO), `cancelled_by`(user_id). **E21 Ledger** (UPDATE 2026-07-03): refund otomatis diposting sbg `payments` negatif (`type="refund"`, `method="refund"`, `amount<0`) — IDEMPOTENT per booking; paid_amount berkurang via recompute. Denda (`cancellation_fee`) tetap MEMO (tidak diposting jurnal terpisah). Detail: `memory/HANDOFF_E21_REFUND.md`.
### trips
`id(trp_)`, `booking_id`, `vehicle_id`, `driver_id`, `status`(standby|to_pickup|on_trip|completed), `start_at`, `end_at`, `revenue`(num), `profit`(num), `distance_km`(num), `created_at`; **E3 dispatch:** `dest_name`, `dest_lat`(num,geocode), `dest_lng`(num,geocode), `dest_display`(str), `assigned_at`, `enroute_at`, `arrived_at`, `pod`{photo_url(/api/uploads/pod/..),recipient_name,note,at,by}; **E8 driver workspace:** `driver_ack_at`(ISO — driver konfirmasi tugas); **E9 trip/km:** `odometer_start`(num), `odometer_end`(num), `distance_basis`(odometer|osrm), `est_distance_km`(num, estimasi OSRM saat assign). distance_km diisi saat checkout (odometer end-start, fallback est_distance_km). vehicles.odometer auto-update dari odometer_end.
### locations (time-series)
`id(loc_)`, `trip_id`, `driver_id`, `vehicle_id`, `lat`(-90..90), `lng`(-180..180), `speed`, `heading`, `timestamp`(ISO)
### payments
`id(pay_)`, `booking_id`, `amount`(num), `type`(dp|settlement|refund), `method`(transfer|tunai|kartu|refund|…), `note`, `recorded_by`, `paid_at`. **E21 Refund Ledger:** `type="refund"` + `method="refund"` + `amount < 0` → dibuat otomatis oleh `POST /api/bookings/{id}/cancel` bila `refund_amount>0`, IDEMPOTENT per booking (tidak duplikat pd retry cancel). paid_amount booking direkompute (Σ payments incl. negatif) via `services.finance.recompute_booking_payment` — INV-2 & INV-3 tetap terjaga.
### expenses
`id(exp_)`, `trip_id`|`booking_id`, `category`(bbm|tol|uang_jalan|gaji_driver|other), `amount`(num>0), `note`, `recorded_by`, `created_at`; **E11 payroll:** `payout_id`(dpo_, nullable), `driver_id`(drv_, nullable), `paid`(bool), `paid_at`(ISO) — expense kategori `gaji_driver` dibuat saat payout DISETUJUI (akrual→P&L) lalu `paid=true` saat DIBAYAR (kas)
### invoices
`id(inv_)`, `number`(INV-YYYY-0001), `booking_id`, `customer_id`, `customer_name`, `booking_code`, `amount`(num), `type`(booking|cancellation_fee), `status`(draft|sent|partial|paid), `issued_at`, `due_at`, `paid_at`(ISO, saat status=paid), `notes`, `reconciled_at`(ISO, diisi saat sync E5)
  · **E26 (Cancellation Invoice)**: saat `POST /api/bookings/{id}/cancel` dgn `cancellation_fee>0`, invoice `type="cancellation_fee"` `status="paid"` otomatis dibuat (idempotent per booking). Sebagai paper trail — TIDAK menaikkan P&L revenue lagi (revenue dihitung dari Σ payments; denda sudah tercakup di residual `paid_amount − refund_amount`).
  · **E5 (Finance Automation)**: status `partial` ditambahkan; `sync_invoice_statuses` menyetel status mengikuti Σ pembayaran (paid/partial/sent) + `reconciled_at`. TIDAK ada koleksi baru — P&L (incl. maintenance), rekonsiliasi, arus kas & proyeksi dihitung on-the-fly dari `payments`/`expenses`/`maintenance_records`/`invoices`/`bookings`/`trips`/`vehicles`. Reminder AR memakai Event Bus E1 (`invoice.overdue`).
### notification_tasks
`id(ntf_)`, `dedupe_key`(unik per skenario+hari), `type`(document_reminder|lead_followup|booking_reminder|reminder_h7|reminder_h3|reminder_h1|payment|departure), `title`, `body`, `ref_type`(vehicle|lead|booking), `ref_id`, `booking_id`|`lead_id`(opsional), `due_at`(ISO), `scheduled_at`(ISO), `status`(pending|read|dismissed|sent|cancelled), `target_role`(manager|owner|ops_admin|driver|all|null), `target_user_id`(usr_, nullable), `channel`(in_app|internal|whatsapp), `created_at`, `read_at`
### broadcasts
`id(brd_)`, `title`, `segment`(rule), `message`, `scheduled_at`, `status`(draft|scheduled|sent), `recipients_count`
### maintenance_records
`id(mnt_)`, `vehicle_id`, `vehicle_name`(snapshot), `type`(servis|kir|pajak|perbaikan|lainnya), `title`, `description`, `scheduled_date`(ISO), `start_date`(ISO, window mulai), `end_date`(ISO, window selesai), `odometer`(num), `cost`(num), `workshop`, `workshop_id`(wsh_, nullable — ref master vendor/bengkel E8), `status`(scheduled|in_progress|done|cancelled), `note`, `completed_at`, `created_by`, `created_at`
### workshops
`id(wsh_)`, `name`, `phone`, `address`, `city`, `specialties[]`(mis. servis|rem|ac|body), `note`, `active`(bool), `created_at`
  · **E8 (Master Vendor/Bengkel)**: CRUD owner/ops_admin (read semua role). Dipakai saat menjadwalkan perawatan (`maintenance_records.workshop_id` → snapshot nama ke `workshop`).
### service_types
`id(svt_)`, `key`(slug unik, dipakai sbg `maintenance_records.type`), `name`, `default_interval_km`(num,opsional), `default_interval_days`(int,opsional), `active`(bool), `created_at`
  · **E10 (Master Jenis Service configurable)**: CRUD owner/ops_admin (read semua role). Selain jenis bawaan (servis/kir/pajak/perbaikan/lainnya), jenis aktif boleh dipakai sebagai `type` saat membuat perawatan.
### driver_payouts
`id(dpo_)`, `driver_id`(drv_), `driver_name`(snapshot), `period_type`(monthly|weekly|per_trip), `period_start`(YYYY-MM-DD), `period_end`(YYYY-MM-DD), `trips_count`(int), `total_km`(num), `total_revenue`(num), `revenue_base`(trip|booking), `base_salary`(num), `commission_trip`(num), `commission_pct`(num), `allowance_km`(num), `gross`(num), `bonuses[]`({label,amount}), `deductions[]`({label,amount}), `bonus_total`(num), `deduction_total`(num), `total`(num), `status`(draft|approved|paid), `approver_id`(usr_,nullable), `approver_name`, `approved_at`, `paid_at`, `expense_id`(exp_,nullable), `snapshot_comp`(obj), `notes`, `created_at`, `updated_at`
  · **E11 (Driver Payroll/HR Lite)**: akses section `finance` (owner/ops_admin). Generator akrual dari trip SELESAI dalam periode + gaji pokok & komponen kompensasi (`drivers.comp`). Alur draft→approved→paid; approve buat expense `gaji_driver` (akrual P&L), pay tandai expense lunas (kas). Hanya draft yang bisa diubah/hapus. Slip PDF+Excel.
### trip_shares
`id(shr_)`, `token`(rahasia, untuk URL publik), `trip_id`(trp_), `vehicle_id`(veh_, nullable snapshot), `label`, `expires_at`(ISO), `revoked`(bool), `revoked_at`, `created_by`(usr_), `last_accessed_at`, `access_count`(int), `created_at`
### pickup_points (master titik jemput — INV-REF-02 batch 2)
`id(pkp_)`, `name` (unik case-insensitive), `created_at`
Relasi: `bookings.origin` menyimpan NAMA KANONIK dari master ini (validator `refs.origin_or_400`;
quick-add via `POST /api/pickup-points`).

### destinations (public content)
`id(dst_)`, `slug`, `name`, `region`(jawa_*|bali), `description`, `hero_image`, `gallery[]`, `hotel_recommendations[]`({name,rating,price_range}), `popular`(bool), `created_at`
  · **P10/FASE 3 (destinasi immersif)**: `intro`, `highlights[]`, `itinerary[]`({day,title,detail}), `route_points[]`({name,lat,lng,note}), `faqs[]`({q,a}), `best_time`, `lat`(num), `lng`(num), `tour_scenes[]`({id,label,panorama,thumbnail,links[]})
### articles (blog)
`id(art_)`, `slug`, `title`, `excerpt`, `body`(paragraf dipisah `\n\n`), `cover_image`, `author`, `tags[]`, `published`(bool), `published_at`
  · **P10/FASE 4 (blog editorial)**: `category`(Tips|Itinerary|Korporat|Destinasi), `featured`(bool, story sorotan), `read_minutes`(int, estimasi waktu baca)
### testimonials
`id(tst_)`, `customer_name`, `rating`(0-5), `body`, `trip`, `photo`, `published`(bool)
### audit_logs
`id`, `actor_id`, `action`, `entity_type`, `entity_id`, `before`, `after`, `timestamp`
### settings
`key`(unik), `value` — kunci: `company_info`, `pricing_defaults`(dp_percent/cancellation_policy/min_rental_hours), `pricing_rules`(day_rates per tipe/driver_fee_per_day/fuel_per_km/toll_parking_per_day/weekend_surcharge_percent/holiday_surcharge_percent/dp_percent/rounding — Pricing Engine B1), `operational`(holidays[]/work_hours), `map_provider`
### user_onboarding
`user_id`, `tasks[]`, `completed[]`
### counters
`id`(scope unik: `booking` | `invoice:<YYYY>` | `quotation:<YYYY>`), `seq`(int) — sumber nomor seri atomik (`$inc`) untuk BK/INV/QUO (INV-8, anti-balapan). Invoice & quotation reset per tahun.
### quotations
`id`(quo_), `number`(QUO-<YYYY>-####), `lead_id`(FK→leads, opsional), `customer_id`(FK→customers, opsional), `customer_name`, `phone`, `phone_normalized`(+62, B2/B4), `email`, `destination`, `trip_date`, `pax`, `items[]`{label,amount}, `subtotal`, `total`, `status`(draft|sent|accepted|rejected|expired|converted), `valid_until`, `notes`, `booking_id`(FK→bookings, setelah convert), `sent_at`/`accepted_at`/`rejected_at`(opsional), `created_by`, `created_at`, `updated_at`
### packages
`id`, `slug`, `name`, `description`, `destination`, `days`, `price_from`, `includes[]`, `image_url`, `active`, `created_at`
### promos
`id`, `code`, `title`, `description`, `discount_type`(percent|amount), `discount_value`, `valid_until`, `active`, `created_at`
### events
(E1 — Event Bus) `id`(evt_), `type`(lead.created|quotation.sent|booking.confirmed|payment.recorded|booking.departure_due|trip.started|trip.completed|invoice.overdue|doc.expiring|wa.inbound|trip.assigned|booking.departure_confirmed|trip.enroute|trip.arrived), `payload`{...}, `source`, `ref_type`, `ref_id`, `dedupe_key`(idempotent, opsional), `processed`(bool), `runs_created`, `created_at`
### automation_rules
(E1 — Automation Engine) `id`(aur_), `name`, `description`, `event_type`(→events.type), `enabled`(bool), `system`(bool), `conditions[]`{field,op(eq|ne|in|contains|exists|gt|lt),value}, `actions[]`{type(send_wa|create_notification|create_task|assign_agent|schedule_followup),params}, `run_count`, `last_run_at`, `created_at`, `updated_at`
### automation_runs
(E1 — log eksekusi) `id`(arn_), `rule_id`(FK→automation_rules), `rule_name`, `event_id`(FK→events), `event_type`, `status`(success|failed|skipped), `actions[]`{type,status,detail}, `dedupe_key`(unik per rule:event), `message`, `created_at`

> **WA in-app (E1)**: koleksi `conversations` diperluas (`wa_opt_in`, `session_expires_at`, `total_cost`) & `messages` (`direction` in|out, `wa_message_id`, `cost`, `template_key`, `provider`, `source`). Konfigurasi & template WA disimpan di `settings` (key `wa_config`, `wa_templates`).

### segments
(E2 — segmentasi audiens dinamis) `id`(seg_), `name`, `audience`(lead|customer), `criteria`{source,stage,score_band,rfm_segment,lifecycle,type,city,min_value,wa_opt_in,last_activity_days,q}, `description`, `system`(bool), `created_at`, `updated_at`
### sequences
(E2 — nurturing/drip) `id`(seq_), `name`, `description`, `audience`(lead|customer), `enabled`(bool), `steps[]`{delay_hours,action(send_wa|create_task|create_notification),template_key,text}, `stats`{enrolled,completed}, `created_at`, `updated_at`
### sequence_enrollments
(E2) `id`(enr_), `sequence_id`(FK→sequences), `sequence_name`, `audience`, `target_id`(lead/customer id), `name`, `phone`, `step_index`, `status`(active|completed|stopped), `next_run_at`, `enrolled_at`, `last_step_at`, `history[]`
### campaigns
(E2 — broadcast WA nyata tersegmentasi) `id`(cmp_), `name`, `channel`(whatsapp), `audience`, `segment_id`(FK→segments, opsional), `segment_snapshot`{audience,criteria}, `template_key`, `message`, `scheduled_at`, `status`(draft|scheduled|sending|sent|failed), `stats`{total,sent,failed,skipped,cost}, `created_by`, `created_at`, `sent_at`
### campaign_recipients
(E2) `id`(cre_), `campaign_id`(FK→campaigns), `target_id`, `name`, `phone`, `status`(pending|sent|skipped_optout|failed), `cost`, `conversation_id`, `message_id`, `error`, `created_at`
### geocode_cache
(E3 — cache hasil geocoding tujuan via OSM Nominatim, hemat rate-limit + idempotent) `q`(query ternormalisasi, unik), `lat`(num), `lng`(num), `display_name`, `provider`(nominatim), `created_at`
### partners
(E16 — master travel mitra utk Pinjam Armada) `id`(ptn_), `name`, `pic`, `phone`, `email`, `city`, `address`, `rating`(num 0-5), `notes`, `status`(active|inactive), `created_at`
  · **AP (utang) dinamis**: `ap_total`(Σ cost subcharter confirmed+settled), `ap_paid`(Σ partner_settlements.amount), `ap_outstanding`(=total−paid), `subcharter_count`, `vehicle_count`. Section RBAC `partners` (owner/ops_admin).
### subcharters
(E16 — order pinjam unit dari mitra) `id`(sbc_), `code`(SC-####), `booking_id`(FK→bookings), `booking_code`, `partner_id`(FK→partners), `partner_name`, `vehicle_id`(FK→vehicles, nullable=unit mitra), `vehicle_label`, `start_datetime`(ISO), `end_datetime`(ISO), `cost`(num, biaya ke mitra=COGS), `status`(requested|confirmed|settled|cancelled), `note`, `expense_id`(exp_, nullable), `confirmed_at`, `settled_at`, `created_at`
  · **COGS**: saat confirm → buat `expenses`(category `sewa_mitra`, `booking_id`[+`trip_id`]) → P&L per booking/trip (INV-5). Anti-overlap unit mitra antar sub-charter aktif. Event `subcharter.requested`/`subcharter.confirmed` → WA ke MITRA.
### partner_settlements
(E16 — pelunasan/pembayaran ke mitra) `id`(pst_), `partner_id`(FK→partners), `partner_name`, `subcharter_id`(FK→subcharters, nullable), `amount`(num), `method`(transfer|cash|other), `note`, `paid_at`(ISO), `recorded_by`(usr_), `created_at`

> **CRM Growth (E2)**: koleksi `leads` diperluas (`score`, `score_band`, `score_factors`, `first_response_at`, `first_response_due_at`, `sla_status`) & `customers` (`rfm_segment`, `lifecycle`, `recency_days`, `frequency`, `lifetime_value`). Konfigurasi growth di `settings` key `crm_growth`.

> **BI & Management Cockpit (E4)**: read-only — TIDAK menambah koleksi baru. Belanja iklan manual disimpan di `settings` key **`marketing_spend`** = `{items:[{channel,amount}], note, updated_at}` (untuk CPL/CAC/ROAS). Agregasi (funnel, channel ROI, fleet ROI, AR aging, retensi, forecast moving-average) dihitung on-the-fly dari koleksi yang ada (`payments`/`expenses`/`bookings`/`leads`/`trips`/`vehicles`/`drivers`/`customers`/`invoices`).

---

## 3. INVARIAN WAJIB (di-enforce `verify_data_integrity.py`)
| ID | Invarian | RC |
|----|----------|----|
| INV-1 | `booking.total_amount == base_price + Σ add_ons.amount` | RC-2 |
| INV-2 | `booking.paid_amount == Σ payments[booking].amount` dan `paid_amount <= total_amount` | RC-2/17 |
| INV-3 | Derivasi `payment_status`: `lunas` jika paid≥total; `dp` jika 0<paid<total; `belum_bayar` jika paid==0; `selesai` jika `status==completed` | RC-17 |
| INV-4 | **Anti double-booking**: untuk `vehicle_id` sama, tidak ada 2 booking status ∈{hold,confirmed,ongoing} yang `[start,end]` overlap (E18: `hold` mereservasi armada) | RC-16 |
| INV-5 | `trip.profit == trip.revenue − Σ expenses[trip].amount` | RC-18 |
| INV-6 | `locations` per `trip_id`: `timestamp` monotonik naik; lat/lng dalam rentang valid | RC-19 |
| INV-7 | `lead.stage ∈ {new,contacted,quoted,negotiation,won,lost}` | RC-20 |
| INV-8 | Number-series unik & monotonik: `bookings.code`, `invoices.number` tak duplikat | RC-5 |
| INV-9 | **Intent KPI**: `dashboard.active_bookings == len(bookings status∈{confirmed,ongoing})`; `dashboard.vehicles == len(vehicles)` | RC-7 |
| INV-10 | Snapshot: `booking.customer_name/vehicle_name/driver_name` tidak null saat status≥confirmed | RC-6 |
| INV-21 | **Maintenance window memblok booking (DUA ARAH, E27)**: untuk `vehicle_id` sama, tidak ada booking aktif ∈{hold,confirmed,ongoing} yang `[start,end]` overlap dengan maintenance window ∈{scheduled,in_progress} yang punya `start_date`+`end_date`. Ditegakkan **dua arah**: jalur booking menolak armada yang sedang dirawat, DAN `POST`/`PATCH /api/maintenance` menolak (400) window yang menabrak keberangkatan aktif (`routers/maintenance.py::_assert_no_departure_clash`, dibungkus `vehicle_lock`). | RC-16 |
| INV-22 | **Share token sah**: `trip_shares` aktif (dipakai publik) wajib `revoked==false` dan `expires_at` > now; token unik | RC-5 |
| INV-23 | **Message FK**: setiap `messages.conversation_id` merujuk `conversations` yang ada (tak ada pesan yatim) | RC-6 |

---

## 4. ATURAN PERTUMBUHAN
Tambah koleksi/field ⇒ (1) update daftar kanonik + alias di sini, (2) `CANONICAL_COLLECTIONS` di `verify_contract.py`, (3) `Concept(...)` + invarian di `verify_data_integrity.py`, (4) `known_collections` di `validate_compliance.py`. Bila tidak → gate membusuk.
C-18 |
| INV-6 | `locations` per `trip_id`: `timestamp` monotonik naik; lat/lng dalam rentang valid | RC-19 |
| INV-7 | `lead.stage ∈ {new,contacted,quoted,negotiation,won,lost}` | RC-20 |
| INV-8 | Number-series unik & monotonik: `bookings.code`, `invoices.number` tak duplikat | RC-5 |
| INV-9 | **Intent KPI**: `dashboard.active_bookings == len(bookings status∈{confirmed,ongoing})`; `dashboard.vehicles == len(vehicles)` | RC-7 |
| INV-10 | Snapshot: `booking.customer_name/vehicle_name/driver_name` tidak null saat status≥confirmed | RC-6 |
| INV-21 | **Maintenance window memblok booking (DUA ARAH, E27)**: untuk `vehicle_id` sama, tidak ada booking aktif ∈{hold,confirmed,ongoing} yang `[start,end]` overlap dengan maintenance window ∈{scheduled,in_progress} yang punya `start_date`+`end_date`. Ditegakkan **dua arah**: jalur booking menolak armada yang sedang dirawat, DAN `POST`/`PATCH /api/maintenance` menolak (400) window yang menabrak keberangkatan aktif (`routers/maintenance.py::_assert_no_departure_clash`, dibungkus `vehicle_lock`). | RC-16 |
| INV-22 | **Share token sah**: `trip_shares` aktif (dipakai publik) wajib `revoked==false` dan `expires_at` > now; token unik | RC-5 |
| INV-23 | **Message FK**: setiap `messages.conversation_id` merujuk `conversations` yang ada (tak ada pesan yatim) | RC-6 |

---

## 4. ATURAN PERTUMBUHAN
Tambah koleksi/field ⇒ (1) update daftar kanonik + alias di sini, (2) `CANONICAL_COLLECTIONS` di `verify_contract.py`, (3) `Concept(...)` + invarian di `verify_data_integrity.py`, (4) `known_collections` di `validate_compliance.py`. Bila tidak → gate membusuk.

---

## 5. KOLEKSI MARKETING & ADS (FASE F3–F7)

> Ditambahkan sesi F3/F4 (E29+). Nilai uang dari platform disimpan **mentah** (micros / satuan
> terkecil) + `currency` akun — JANGAN dikonversi diam-diam (akun iklan bisa non-IDR).

| Koleksi | Prefix id | Isi | Kunci unik / index |
|---------|-----------|-----|--------------------|
| `conversion_events` | `cvn_` | Outbox konversi server-side (Meta CAPI + Google Data Manager): `provider`, `event_key`, `kind`, `ref_id`, `value`, `identifiers`, `action_source`, `consent_granted`, `status` (pending/success/failed/dead/skipped), `attempts`, `next_retry_at`, `last_error` | **unique `(provider, event_key)`** · `(status, next_retry_at)` · `created_at` |
| `ads_accounts` | `adacc_` | Cache metadata akun iklan: `provider`, `account_id`, `name`, `currency`, `timezone`, `status`, `synced_at` | unique `(provider, account_id)` |
| `ads_entities` | `ade_` | Kampanye/adset/iklan hasil sinkron: `level`, `entity_id`, `parent_id`, `name`, `status`, `objective`, `daily_budget`, `resource_name`, `budget_resource` | unique `(provider, level, entity_id)` |
| `ads_metrics_daily` | `adm_` | Metrik harian: `spend`, `spend_micros`, `currency`, `impressions`, `clicks`, `reach`, `platform_leads`, `platform_conversion_value`, `actions{}` | **unique `(provider, level, entity_id, date)`** → tarik ulang idempoten |
| `ads_sync_runs` | `adr_` | Jejak tarikan data: `since`, `until`, `level`, `status`, `rows`, `reason`, `usage` (header kuota) | `created_at` |
| `ad_touches` | `adt_` | Klik iklan teridentifikasi: `click_id` (gclid/fbclid/ctwa_clid/leadgen), `provider`, `kind`, `ad_id`, `adset_id`, `campaign_id`, `lead_id` | unique sparse `click_id` |
| `audience_syncs` | `aus_` | Riwayat sinkron audiens: `segment_id`, `provider`, `mode`, `total`, `eligible`, `consent_filtered`, `uploaded`, `batches`, `audience_id`, `status` | `created_at` · `(segment_id, provider)` |
| `platform_leads` | `plead_` | Lead mentah dari Meta Lead Ads: `leadgen_id`, `form_id`, `page_id`, `ad_id`, `adset_id`, `campaign_id`, `fields{}`, `fetch_status`, `lead_id` | **unique `leadgen_id`** → dedup pengiriman ganda webhook |

**Perluasan koleksi `leads` (atribusi level iklan):** `ad_platform`, `ad_campaign_id`,
`ad_adset_id`, `ad_id`, `ad_form_id`, `platform_lead_id`, `ctwa_clid`
(+ index sparse `ad_campaign_id`, `ad_id`). Tanpa field ini, ROAS **per iklan** tidak mungkin
dihitung — channel saja tidak menjawab "iklan mana yang menghasilkan booking".

**Kunci join ROAS nyata:**
`ads_metrics_daily.entity_id` ⟷ `leads.ad_campaign_id|ad_adset_id|ad_id` ⟷
`leads.converted_customer_id` ⟷ `bookings.customer_id` (status confirmed/ongoing/completed) ⟷
`payments`.

### FASE F8 — Landing Page Builder (halaman tujuan iklan)

- **landing_pages** — `id`, `title`, `slug`(unique), `segment`(armada|destinasi), `template`,
  `status`(draft|published), `blocks[]`, `theme`, `seo`{title,description,og_image},
  `tracking`{utm_default,conversion_label}, `ab`{enabled,goal,min_sample,variants[]},
  `duplicated_from`, `published_at`, `created_by`, `created_at`, `updated_at`.
  · **blocks[]** = SSOT bentuk blok ada di `services/landing_blocks.BLOCK_TYPES` (17 tipe).
    Tiap blok: `{id, type, hidden, device(all|desktop|mobile), props{…}}`. Nama props bersifat
    KANONIK dan ditegakkan guardrail **INV-LP-02** (template & renderer wajib memakai nama yang sama).
  · **ab.variants[]** = `{id(A|B|C), name, weight(0-100), overrides{title,subtitle,eyebrow,cta_label}}`.
    Varian pertama SELALU tanpa override (halaman asli) supaya perbandingan punya titik nol.
  · Aturan layak-terbit (**INV-LP-01**): slug + judul + `seo.title` + minimal satu blok konversi
    (`lead_form|cta_band|wa_cta|hero_media|search_hero` yang tidak disembunyikan); blok `video`
    dengan berkas wajib punya `poster`.
- **media_assets** — `id`, `kind`(image|video), `storage_backend`(local|objstore), `storage_path`,
  `thumb_path`, `size`, `width`, `height`, `content_type`, `original_filename`, `alt`,
  `deleted`(soft-delete), `deleted_at`, `uploaded_by`, `created_at`.
  · URL baca TIDAK disimpan di dokumen; dibangun satu pintu oleh `routers/landing.media_url()`
    menjadi `/api/public/media/{id}` (`?thumb=1` untuk versi kecil). Jalur berkas internal tidak
    pernah dikirim ke klien. Dijaga **INV-MEDIA-01/02**.
- **landing_stats** — agregat harian per varian: unique(`page_id`,`variant_id`,`date`) +
  `views`, `cta_clicks`, `leads`, `created_at`, `updated_at`. Dipilih agregat (bukan satu baris per
  kunjungan) agar koleksi tidak meledak tanpa nilai analitik tambahan, dan `$inc` upsert membuatnya
  idempoten saat permintaan diulang.
- **leads** (tambahan F8) — `source="landing_page"`, `landing_page_id`, `landing_slug`,
  `landing_variant`, `landing_block_id`, `click_ids`{gclid,fbclid,ttclid,ctwa_clid,wbraid,gbraid},
  `lp_dedupe_key`(unique sparse = sha256(page_id|telepon|tanggal|idempotency_key)).
  · `lp_dedupe_key` adalah pengaman ANTI-LEAD-GANDA tingkat database: klik dobel atau retry jaringan
    tetap menghasilkan satu lead, sehingga sales tidak menelepon orang yang sama dua kali.

---

## 6. PEMESANAN ONLINE V1 (Booking Publik ala rentcar) — 2026-08-12

Alur: tamu **cari → pilih unit → isi data → pesanan dibuat** (kode booking langsung) →
**instruksi DP + unggah bukti** → ops verifikasi → `hold` otomatis jadi `confirmed`.
Tanpa akun pelanggan: halaman status diakses lewat **kode booking + `public_token`** (atau
kode + nomor WhatsApp lewat `POST /api/public/booking/lookup`).

### Field BARU pada koleksi yang sudah ada

- **vehicles** — `day_rate` (integer rupiah; tarif per unit yang MENIMPA tarif per tipe di
  `settings.pricing_rules.day_rates`) · `publish_to_web` (bool). `publish_to_web` WAJIB `True`
  **eksplisit** agar unit dijual online — nilai kosong TIDAK lagi dianggap "boleh dijual"
  (lihat INV-BOOK-02 & pelajaran "Smoke Vehicle" di `memory/INVARIANTS.md`). Data lama
  diselaraskan sekali oleh `scripts/migrate_booking_v1.py`.
- **bookings** — `service` (`daily_rental|airport_transfer|request_only`) · `service_label` ·
  `route_id`/`route_name` (antar-jemput) · `pax` · `pickup_address` · `contact_phone` /
  `contact_email` · `source` (`web_booking` untuk pemesanan online, `public` untuk permintaan
  penawaran) · `price_breakdown[]` (salinan rincian yang DILIHAT tamu — bukti "tampil ==
  tersimpan") · `promo_code`/`promo_id`/`promo_discount` · `dp_percent`/`dp_amount` ·
  `hold_expires_at`/`hold_hours` · `public_token` (rahasia halaman status) ·
  `public_idempotency_key` (unik; 1 klik ganda = 1 pesanan) · `proof_status`
  (`pending|verified|rejected`) · `approved_at`/`approved_by` (mode `ops_approval`).
- **customers** — dibuat/dipakai ulang lewat `services/identity.ensure_customer`
  (dedupe `phone_normalized`, INV-IDENT-01), `notes` menandai asal "pemesanan online".

### Koleksi BARU

### payment_proofs
(prefix `ppf_`) — bukti transfer DP dari tamu: `id`, `booking_id`, `booking_code`,
`customer_name`, `media_id` + `media_url` (Media Library, satu pintu), `amount_claimed`
(klaim tamu — BUKAN nominal sah), `sender_name`, `bank`, `note`,
`status`(pending|verified|rejected), `amount_verified`, `payment_id`, `verified_by`,
`verified_at`, `reject_reason`, `created_at`.
· Verifikasi TIDAK menulis `payments` sendiri melainkan memanggil
`routers.payments.create_payment` (idempotency-key `proof:{proof_id}`) supaya seluruh
invarian uang tetap berlaku: anti-overpay atomik (INV-2), derivasi `payment_status`
(INV-3), audit, event `payment.recorded`, dan promosi `hold → confirmed` (DP-gate E18).

### transfer_routes
(prefix `trt_`) — rute antar-jemput bandara: `id`, `code`, `name`, `from_label`, `to_label`,
`airport_code`, `rates{vehicle_type: rupiah}` (tarif **FLAT**), `duration_minutes`, `notes`,
`active`, `position`.
· Tipe armada yang TIDAK ada di `rates` = **tidak dilayani** pada rute itu (server
mengembalikan "Tidak melayani rute ini", bukan mengarang harga default).

**promos** (sudah ada, diperkuat) — syarat promo kini DATA yang ditegakkan server:
`active`, `valid_from`/`valid_until`, `discount_type`(percent|amount), `value`, `min_days`,
`vehicle_types[]`, `services[]`, `max_uses`, `used_count`.

### Kunci settings BARU

- **settings.booking_flow** — `mode` (`hold_dp|ops_approval`), `hold_hours`(1–168),
  `approval_hold_hours`(1–168), `approval_sla_hours`(1–168), `min_lead_hours`(0–168),
  `max_advance_days`(1–730), `min_days`(1–30), `max_days`(1–90),
  `transfer_buffer_minutes`(0–720), `enabled_services[]`,
  `payment`{`bank_accounts[]`{bank,number,holder}, `qris_media_id`, `instructions`},
  `cancellation_policy`, `terms`. SSOT bentuk + pagar nilai: `services/booking_flow.py`.
- **settings.pricing_rules** — `dp_percent` di sini adalah **SATU-SATUNYA** sumber DP
  (`services.pricing.get_dp_percent`); `pricing_defaults.dp_percent` hanya cermin data lama
  dan disinkronkan otomatis oleh `routers/settings.py`. `fuel_per_km` **usang** — komponen
  jarak sudah dihapus dari mesin harga (dijaga **INV-PRICE-01**).

### Relasi & invarian tambahan

```
transfer_routes ─(route_id)→ bookings ─(booking_id)→ payment_proofs ─(payment_id)→ payments
vehicles.day_rate ⟶ services/pricing.resolve_day_rate ⟶ quote.total ⟶ bookings.total_amount
```
- **INV-BOOK-02** — pesanan publik WAJIB: unit lolos `publishable_vehicles`, harga dihitung
  ulang server (`build_quote`), `assert_free` (booking aktif **dan** jendela perawatan), dan
  penulisan di dalam `vehicle_lock`. Klien tidak pernah mengirim harga.
- **INV-PRICE-01** — harga = hari × tarif (+ surcharge tanggal + add-on − promo). Tanpa
  komponen jarak. `dp_amount` = `total × dp_percent`.
- **INV-STR-01** — semua field teks berbatas `max_length` (nama 60.000 karakter pernah
  tersimpan dan merusak tata letak tabel ERP — lihat BUG-0114).

---

## 7. CMS-CW2 — Siklus Terbit, Dua Bahasa, Funnel Ulasan & Analitik Konten (2026-08-17)

Menutup CMS-05 … CMS-09 + defect A1–A3 dari `CMS_REVIEW_AND_ENHANCEMENT_PLAN.md`.
SSOT kode: `services/content_publish.py`, `services/i18n.py`, `services/richtext.py`,
`services/reviews.py`, `services/content_stats.py`, `services/promos.py`.

### Field BARU pada koleksi konten yang sudah ada

**destinations · packages · articles** (siklus terbit, CMS-05):
`status` (`draft|scheduled|published`), `publish_at` (ISO UTC), `published_at`.
· Boolean lama TETAP disinkronkan server (`articles.published`, `packages.active`) supaya
  laporan/sitemap/seed lama tidak rusak; dokumen TANPA `status` dinilai dari boolean lama.
· Visibilitas publik dihitung SATU predikat bersama `content_publish.visibility_filter()`
  yang dipakai daftar, detail, DAN sitemap — mustahil berbeda pendapat.
· `scheduled` yang `publish_at`-nya sudah lewat LANGSUNG dianggap tayang; `publish_due()`
  (penjadwal `server.py`) hanya merapikan status di database.

**destinations · packages · articles · promos** (dua bahasa, CMS-06):
`translations` = `{ "en": { field: teks|list } }`.
· Field yang boleh diterjemahkan DIBATASI whitelist `services/i18n.TRANSLATABLE`
  (destinations: name/description/intro/best_time/meta_*; packages: name/description/includes/meta_*;
  articles: title/excerpt/body/meta_*; promos: title/description/meta_*).
· `localize()` menimpa field dasar HANYA bila terjemahan tidak kosong → halaman English
  selalu punya fallback Indonesia (tak pernah berlubang).
· Bahasa dasar (id) TIDAK pernah disimpan di dalam `translations`.

**articles.body** (rich text, CMS-09): HTML **tersanitasi server** (`richtext.sanitize`,
allowlist tag/atribut/protokol; blok `script/style/iframe/object/embed` dibuang BESERTA isinya).
Teks polos artikel lama tetap didukung (renderer publik mendeteksi format).

**promos** (A2 — syarat sebagai DATA): `valid_from`, `valid_until`, `min_days`, `min_amount`,
`vehicle_types[]`, `services[]`, `weekend_only`, `max_uses`, `used_count` (read-only di CMS).
· Semua ditegakkan `services/promos.evaluate` saat checkout; `used_count` dikonsumsi ATOMIK
  (`promos.consume`) sehingga kuota mustahil kelebihan pada dua pemesan bersamaan.

### content_previews

`id(cpv_)`, `token`(unik), `resource`(destinations|packages|articles), `item_id`, `slug`,
`created_by`, `created_at`, `expires_at` (default +24 jam).
· Dipakai `?preview=<token>` pada halaman publik untuk membuka SATU dokumen yang belum tayang.
  Token TIDAK membuka koleksi lain dan mati sendiri saat kedaluwarsa.

### review_requests

`id(rvq_)`, `token`(unik), `booking_id`→bookings, `booking_code`, `customer_id`, `customer_name`,
`phone`, `route`, `status`(`sent|submitted|expired`), `source`, `channel`(`whatsapp_mock`),
`link`, `rating`, `testimonial_id`→testimonials, `created_at`, `sent_at`, `submitted_at`,
`expires_at`.
· Dibuat saat pesanan menjadi `completed` (hook `routers/bookings.py` + jaring pengaman
  penjadwal `reviews.scan_due`). Idempotent per pesanan.
· Pengisian publik → `testimonials` dengan `approved=false`, `source="review"`,
  `booking_code`, `review_request_id` → menunggu moderasi di CMS → tayang.
· **WhatsApp = MOCK**: pesan tercatat di Inbox & Audit Log, tautan ulasan NYATA.

### content_stats

Kunci **(kind, slug)** — koleksi ini SENGAJA tanpa field `id`.
`kind`(`article|destination|package`), `slug`, `title`, `views`, `last_view_at`, `created_at`.
· Anti-inflasi: satu IP dihitung sekali per 30 menit per konten; **IP tidak disimpan**
  (hanya kunci hitung di memori — `services/ratelimit`).
· Atribusi lead/pesanan TIDAK disimpan di sini: dihitung saat diminta dari
  `leads.content_ref` / `bookings.content_ref` (satu sumber kebenaran).
- **BUG-0128** — mesin bersih-bersih data uji WAJIB bisa menghapus dokumen tanpa field `id`
  (koleksi ini contohnya); dulu artefak POC tetap tampil di panel Analitik Konten.

### Relasi

```
bookings ─(booking_id)→ review_requests ─(testimonial_id)→ testimonials(approved=false→true)
articles|destinations|packages ─(slug,kind)→ content_stats
leads.content_ref{kind,slug,title} / bookings.content_ref{kind,slug,title} ⟶ atribusi konten
destinations|packages|articles ─(item_id)→ content_previews(token, expires_at)
```

## 8. CMS-CW3 — Riwayat Versi, Tempat Sampah & Pengalihan URL (2026-08-18)

Menutup sisa gap `G-WORKFLOW` (versioning + rollback) dan risiko SEO terbesar CMS (slug berubah
→ URL lama 404). Tidak ada field baru pada koleksi konten; tiga koleksi BARU:

### content_versions
| Field | Tipe | Catatan |
|---|---|---|
| `id` | str | prefiks `cvr_` |
| `resource` | str | destinations \| packages \| articles \| testimonials \| promos |
| `item_id` | str | id dokumen konten |
| `version` | int | nomor urut per dokumen; **index UNIK** `(resource, item_id, version)` |
| `action` | str | create \| update \| restore |
| `snapshot` | obj | dokumen LENGKAP sesudah perubahan (tanpa `_id`) |
| `changed_fields` | [str] | field yang berbeda dari versi sebelumnya (derau teknis dibuang) |
| `label` / `actor_id` / `actor_name` / `created_at` | str | jejak siapa-melakukan-apa |

- Batas simpan **20 versi terakhir per dokumen** (`MAX_VERSIONS`), sisanya dipangkas `prune()`.
- Pemulihan TIDAK destruktif: hasilnya ditulis sebagai versi baru (rollback bisa di-rollback).
- Pemulihan menyaring field lewat `restorable()` (whitelist resource) → mustahil menyuntikkan
  field asing dari snapshot lama (mass-assignment lewat pintu riwayat).

### content_trash
| Field | Tipe | Catatan |
|---|---|---|
| `id` | str | prefiks `ctr_` |
| `resource` / `item_id` / `label` / `slug` / `slug_field` | str | identitas konten yang dibuang |
| `snapshot` | obj | dokumen utuh (dipulihkan dengan **id yang sama**) |
| `deleted_by` / `deleted_by_name` / `deleted_at` | str | jejak penghapusan |
| `expires_at` | str ISO | `deleted_at + RETENTION_DAYS (30)`; dibuang penjadwal |
| `restored` / `restored_at` / `restored_by` | bool/str | baris yang sudah dipulihkan |

- Hapus = PINDAH koleksi (bukan `deleted_at` di dokumen aslinya) supaya SELURUH kueri publik &
  admin yang sudah ada mustahil lupa menyaring dokumen terhapus.
- Pemulihan SELALU `status = draft` (`published`/`active`/`approved` = false).
- Bentrok slug: 409 apa adanya, atau `?rename=true` → akhiran `-restored` yang dijamin unik.

### content_redirects
| Field | Tipe | Catatan |
|---|---|---|
| `id` | str | prefiks `crd_` |
| `from_path` | str | **index UNIK**; path ternormalkan (tanpa query/fragment/garis miring akhir) |
| `to_path` | str | tujuan; rantai diratakan jadi SATU lompatan |
| `resource` / `item_id` | str | kosong untuk pengalihan manual |
| `kind` | str | auto (slug diubah) \| manual |
| `hits` / `last_hit_at` | int/str | kunjungan yang diselamatkan dari 404 |

### Relasi
```
destinations|packages|articles ─(item_id)→ content_versions / content_trash / content_redirects
content_trash.snapshot.id  = id yang dipulihkan (tautan internal & atribusi analitik tak putus)
content_redirects.from_path → to_path (dipakai GET /api/public/redirect)
```

> Tambah koleksi/field ⇒ update (1) daftar kanonik di dokumen ini, (2) `CANONICAL_COLLECTIONS`
> di `verify_contract.py`, (3) `PREFIX`/`NO_PREFIX` di `verify_schema.py`, (4) `CANONICAL` di
> `validate_compliance.py`, (5) `PURGE_COLLECTIONS` **dan cascade** di `scripts/guardrails/_common.py`, (6) daftar reset di `scripts/seed_data.py` — ditegakkan `INV-CMS-01`.
