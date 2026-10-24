-- Trackback bitemporal store. Append-only: the only UPDATE allowed closes tx_to
-- (plus the two state-machine columns artifacts.status and actions.state, see DECISIONS.md).
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = OFF;

CREATE TABLE IF NOT EXISTS sources(source_id TEXT PRIMARY KEY, uri_r TEXT, system TEXT, kind TEXT, title TEXT);
CREATE TABLE IF NOT EXISTS source_versions(version_id TEXT PRIMARY KEY, source_id TEXT, body TEXT, content_hash TEXT,
  document_date TEXT, tx_from TEXT, tx_to TEXT, supersedes TEXT, correction_id TEXT);  -- the mementos; Memento-Datetime = tx_from
CREATE TABLE IF NOT EXISTS claims(claim_id TEXT PRIMARY KEY, source_id TEXT, entity TEXT, account TEXT, line_item TEXT,
  unit TEXT, period_start TEXT, period_end TEXT);                  -- stable key: (entity, line_item, period, unit)
CREATE TABLE IF NOT EXISTS claim_versions(claim_version_id TEXT PRIMARY KEY, claim_id TEXT, source_version_id TEXT,
  value_num REAL, value_text TEXT, span_start INT, span_end INT,
  valid_from TEXT, valid_to TEXT, tx_from TEXT, tx_to TEXT);
CREATE TABLE IF NOT EXISTS artifacts(artifact_id TEXT, version INT,
  kind TEXT CHECK(kind IN ('number','sentence','forecast_cell','action')),
  run_id TEXT, pinned_at TEXT, period TEXT, line_item TEXT, content TEXT, value_num REAL, formula TEXT,
  conclusions_json TEXT,
  status TEXT,                     -- valid | suspect | stale | unprovable | superseded | compensated
  tx_from TEXT, tx_to TEXT,
  agent_id TEXT, node_kind TEXT, origin TEXT, supersedes_version INT, content_hash TEXT, reason TEXT, approved_by TEXT, metric TEXT, fields_json TEXT,
  PRIMARY KEY(artifact_id, version));
CREATE TABLE IF NOT EXISTS justifications(edge_id TEXT PRIMARY KEY, consumer_id TEXT, consumer_version INT,
  supporter_kind TEXT CHECK(supporter_kind IN ('claim','artifact')), supporter_id TEXT, supporter_version TEXT,
  dep_kind TEXT CHECK(dep_kind IN ('numeric','prose','control')),
  capture TEXT CHECK(capture IN ('tool_log','structured','citation')), validity_predicate TEXT);
CREATE TABLE IF NOT EXISTS reads(read_id TEXT PRIMARY KEY, run_id TEXT, tool_call_id TEXT, uri_m TEXT, source_version_id TEXT,
  memento_datetime TEXT, pinned_at TEXT, http_status INT, ts TEXT);   -- every read, refusals included
CREATE TABLE IF NOT EXISTS corrections(correction_id TEXT PRIMARY KEY, source_id TEXT, old_version TEXT, new_version TEXT,
  kind TEXT CHECK(kind IN ('estimate','error','fact_update')), knowable_at TEXT,
  materiality_verdict TEXT, booking_period TEXT, tx_time TEXT, note TEXT);
CREATE TABLE IF NOT EXISTS claim_diffs(correction_id TEXT, claim_id TEXT, old_cv TEXT, new_cv TEXT,
  change TEXT CHECK(change IN ('changed','unchanged','added','removed')));
CREATE TABLE IF NOT EXISTS impact_findings(correction_id TEXT, artifact_id TEXT, artifact_version INT,
  verdict TEXT CHECK(verdict IN ('invalidated','unaffected','needs_review','unprovable')),
  reason TEXT,
  old_value REAL, new_value REAL, judge_model TEXT, judge_rationale TEXT, cache_key TEXT, hop INT, proposed_rewrite TEXT);
CREATE TABLE IF NOT EXISTS actions(action_id TEXT PRIMARY KEY, artifact_id TEXT, kind TEXT, params_json TEXT, ledger_tx_id TEXT,
  executed_at TEXT, compensator_json TEXT,
  state TEXT, run_id TEXT, proposer TEXT, approver_role TEXT, created_at TEXT);   -- executed | compensation_proposed | approved | compensated | rejected | proposed | blocked
CREATE TABLE IF NOT EXISTS approvals(approval_id TEXT PRIMARY KEY, action_id TEXT, proposer TEXT, approver TEXT,
  decision TEXT, reason TEXT, ts TEXT, CHECK (proposer <> approver));  -- segregation of duties in the schema
CREATE TABLE IF NOT EXISTS ledger_entries(tx_id TEXT, line INT, account TEXT, amount_cents INTEGER, period TEXT,
  orig_period TEXT, memo TEXT, action_id TEXT, approval_id TEXT, correction_id TEXT, ts TEXT, gym TEXT);
CREATE TABLE IF NOT EXISTS llm_cache(cache_key TEXT PRIMARY KEY, request_json TEXT, response_json TEXT, model TEXT, ts TEXT);

-- Additions (not renames): run registry, event log, norms, misstatement log, period locks, vendor master.
CREATE TABLE IF NOT EXISTS runs(run_id TEXT PRIMARY KEY, agent TEXT, task TEXT, pinned_at TEXT, mode TEXT, status TEXT,
  started_at TEXT, finished_at TEXT, turns INT, note TEXT, trigger TEXT, ping_id TEXT, goal TEXT, deliverables_json TEXT, model TEXT, prompt_version TEXT);
CREATE TABLE IF NOT EXISTS events(event_id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, kind TEXT, actor TEXT, summary TEXT, detail_json TEXT, correction_id TEXT, run_id TEXT);
CREATE TABLE IF NOT EXISTS norms(norm_id TEXT, version INT, name TEXT, entity TEXT, rule_json TEXT, evidence_json TEXT,
  status TEXT, valid_from TEXT, approved_by TEXT, tx_from TEXT, tx_to TEXT, PRIMARY KEY(norm_id, version));
CREATE TABLE IF NOT EXISTS misstatement_log(entry_id TEXT PRIMARY KEY, correction_id TEXT, period TEXT, line_item TEXT,
  amount REAL, booked INT, note TEXT, ts TEXT);
CREATE TABLE IF NOT EXISTS periods(period TEXT PRIMARY KEY, locked INT, locked_at TEXT, locked_by TEXT);
CREATE TABLE IF NOT EXISTS vendor_master(vendor_id TEXT, version INT, name TEXT, iban TEXT, domain TEXT, owner TEXT,
  tx_from TEXT, tx_to TEXT, PRIMARY KEY(vendor_id, version));

CREATE INDEX IF NOT EXISTS idx_sv_source ON source_versions(source_id, tx_from);
CREATE INDEX IF NOT EXISTS idx_cv_claim ON claim_versions(claim_id, tx_from);
CREATE INDEX IF NOT EXISTS idx_cv_sv ON claim_versions(source_version_id);
CREATE INDEX IF NOT EXISTS idx_just_consumer ON justifications(consumer_id, consumer_version);
CREATE INDEX IF NOT EXISTS idx_just_supporter ON justifications(supporter_id);
CREATE INDEX IF NOT EXISTS idx_reads_run ON reads(run_id);
CREATE INDEX IF NOT EXISTS idx_findings_corr ON impact_findings(correction_id);
CREATE INDEX IF NOT EXISTS idx_ledger_tx ON ledger_entries(tx_id);

-- Append-only enforcement. DELETE is never allowed. UPDATE only closes tx_to
-- (or advances the two state-machine columns).
CREATE TRIGGER IF NOT EXISTS no_del_sources BEFORE DELETE ON sources BEGIN SELECT RAISE(ABORT,'append-only'); END;
CREATE TRIGGER IF NOT EXISTS no_del_source_versions BEFORE DELETE ON source_versions BEGIN SELECT RAISE(ABORT,'append-only'); END;
CREATE TRIGGER IF NOT EXISTS no_del_claims BEFORE DELETE ON claims BEGIN SELECT RAISE(ABORT,'append-only'); END;
CREATE TRIGGER IF NOT EXISTS no_del_claim_versions BEFORE DELETE ON claim_versions BEGIN SELECT RAISE(ABORT,'append-only'); END;
CREATE TRIGGER IF NOT EXISTS no_del_artifacts BEFORE DELETE ON artifacts BEGIN SELECT RAISE(ABORT,'append-only'); END;
CREATE TRIGGER IF NOT EXISTS no_del_justifications BEFORE DELETE ON justifications BEGIN SELECT RAISE(ABORT,'append-only'); END;
CREATE TRIGGER IF NOT EXISTS no_del_reads BEFORE DELETE ON reads BEGIN SELECT RAISE(ABORT,'append-only'); END;
CREATE TRIGGER IF NOT EXISTS no_del_corrections BEFORE DELETE ON corrections BEGIN SELECT RAISE(ABORT,'append-only'); END;
CREATE TRIGGER IF NOT EXISTS no_del_claim_diffs BEFORE DELETE ON claim_diffs BEGIN SELECT RAISE(ABORT,'append-only'); END;
CREATE TRIGGER IF NOT EXISTS no_del_findings BEFORE DELETE ON impact_findings BEGIN SELECT RAISE(ABORT,'append-only'); END;
CREATE TRIGGER IF NOT EXISTS no_del_actions BEFORE DELETE ON actions BEGIN SELECT RAISE(ABORT,'append-only'); END;
CREATE TRIGGER IF NOT EXISTS no_del_approvals BEFORE DELETE ON approvals BEGIN SELECT RAISE(ABORT,'append-only'); END;
CREATE TRIGGER IF NOT EXISTS no_del_ledger BEFORE DELETE ON ledger_entries BEGIN SELECT RAISE(ABORT,'append-only'); END;
CREATE TRIGGER IF NOT EXISTS no_del_norms BEFORE DELETE ON norms BEGIN SELECT RAISE(ABORT,'append-only'); END;

CREATE TRIGGER IF NOT EXISTS upd_source_versions BEFORE UPDATE ON source_versions
  WHEN NEW.version_id<>OLD.version_id OR NEW.source_id<>OLD.source_id OR NEW.body<>OLD.body OR NEW.tx_from<>OLD.tx_from OR NEW.tx_to=OLD.tx_to
  BEGIN SELECT RAISE(ABORT,'append-only: only tx_to may be closed'); END;
CREATE TRIGGER IF NOT EXISTS upd_claim_versions BEFORE UPDATE ON claim_versions
  WHEN NEW.claim_version_id<>OLD.claim_version_id OR IFNULL(NEW.value_num,-1e300)<>IFNULL(OLD.value_num,-1e300) OR IFNULL(NEW.value_text,'')<>IFNULL(OLD.value_text,'') OR NEW.tx_from<>OLD.tx_from OR NEW.tx_to=OLD.tx_to
  BEGIN SELECT RAISE(ABORT,'append-only: only tx_to may be closed'); END;
CREATE TRIGGER IF NOT EXISTS upd_artifacts BEFORE UPDATE ON artifacts
  WHEN NEW.artifact_id<>OLD.artifact_id OR NEW.version<>OLD.version OR IFNULL(NEW.content,'')<>IFNULL(OLD.content,'') OR IFNULL(NEW.value_num,-1e300)<>IFNULL(OLD.value_num,-1e300) OR IFNULL(NEW.formula,'')<>IFNULL(OLD.formula,'') OR NEW.tx_from<>OLD.tx_from OR (NEW.tx_to=OLD.tx_to AND NEW.status=OLD.status)
  BEGIN SELECT RAISE(ABORT,'append-only: only tx_to or status may change'); END;
CREATE TRIGGER IF NOT EXISTS upd_actions BEFORE UPDATE ON actions
  WHEN NEW.action_id<>OLD.action_id OR NEW.kind<>OLD.kind OR IFNULL(NEW.params_json,'')<>IFNULL(OLD.params_json,'') OR (OLD.ledger_tx_id IS NOT NULL AND IFNULL(NEW.ledger_tx_id,'')<>OLD.ledger_tx_id) OR (OLD.executed_at IS NOT NULL AND IFNULL(NEW.executed_at,'')<>OLD.executed_at)
  BEGIN SELECT RAISE(ABORT,'append-only: only state/compensator may change'); END;
CREATE TRIGGER IF NOT EXISTS upd_norms BEFORE UPDATE ON norms
  WHEN NEW.norm_id<>OLD.norm_id OR NEW.version<>OLD.version OR NEW.rule_json<>OLD.rule_json OR NEW.tx_to=OLD.tx_to
  BEGIN SELECT RAISE(ABORT,'append-only: only tx_to may be closed'); END;
CREATE TRIGGER IF NOT EXISTS upd_ledger BEFORE UPDATE ON ledger_entries BEGIN SELECT RAISE(ABORT,'append-only'); END;
CREATE TRIGGER IF NOT EXISTS upd_approvals BEFORE UPDATE ON approvals BEGIN SELECT RAISE(ABORT,'append-only'); END;
CREATE TRIGGER IF NOT EXISTS upd_reads BEFORE UPDATE ON reads BEGIN SELECT RAISE(ABORT,'append-only'); END;
CREATE TRIGGER IF NOT EXISTS upd_corrections BEFORE UPDATE ON corrections WHEN NEW.correction_id<>OLD.correction_id OR NEW.new_version<>OLD.new_version OR NEW.tx_time<>OLD.tx_time OR NEW.kind<>OLD.kind BEGIN SELECT RAISE(ABORT,'append-only'); END;
CREATE TRIGGER IF NOT EXISTS upd_findings BEFORE UPDATE ON impact_findings BEGIN SELECT RAISE(ABORT,'append-only'); END;
CREATE TRIGGER IF NOT EXISTS upd_justifications BEFORE UPDATE ON justifications BEGIN SELECT RAISE(ABORT,'append-only'); END;
CREATE TRIGGER IF NOT EXISTS upd_claims BEFORE UPDATE ON claims BEGIN SELECT RAISE(ABORT,'append-only'); END;
CREATE TRIGGER IF NOT EXISTS upd_sources BEFORE UPDATE ON sources BEGIN SELECT RAISE(ABORT,'append-only'); END;

-- ---------------------------------------------------------------- Iteration 2: the multi-agent handoff graph and trackback pings
CREATE TABLE IF NOT EXISTS agents(agent_id TEXT PRIMARY KEY, display_name TEXT, ping_endpoint TEXT, model TEXT, prompt_version TEXT, seat TEXT);
CREATE TABLE IF NOT EXISTS consumption_receipts(receipt_id TEXT PRIMARY KEY, consumer_artifact_id TEXT, consumer_version INT, consumed_artifact_id TEXT,
  consumed_version INT, consumed_sha256 TEXT, fields_read_json TEXT, run_id TEXT, agent_id TEXT, ts TEXT);
CREATE TABLE IF NOT EXISTS waves(wave_id TEXT PRIMARY KEY, correction_id TEXT, wave_no INT, started_at TEXT, finished_at TEXT, status TEXT, seeds_json TEXT, stats_json TEXT);
CREATE TABLE IF NOT EXISTS pings(ping_id TEXT PRIMARY KEY, idempotency_key TEXT UNIQUE, correction_id TEXT, wave_id TEXT, root_ping_id TEXT, hop INT,
  causal_chain_json TEXT, target_agent_id TEXT, payload_json TEXT, state TEXT, refusal_code TEXT, created_at TEXT, delivered_at TEXT, responded_at TEXT, attempts INT DEFAULT 0, superseded_by TEXT);
CREATE TABLE IF NOT EXISTS ping_responses(ping_id TEXT, state TEXT, reason TEXT, evidence_json TEXT, new_versions_json TEXT, material_change INT, responded_at TEXT, items_json TEXT);
CREATE TABLE IF NOT EXISTS upstream_challenges(challenge_id TEXT PRIMARY KEY, from_agent_id TEXT, target_artifact_id TEXT, reason TEXT, state TEXT, created_at TEXT, decided_by TEXT, decided_at TEXT, correction_id TEXT);
CREATE TABLE IF NOT EXISTS outbox(event_id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT, payload_json TEXT, created_at TEXT, sent_at TEXT, ping_id TEXT);
CREATE TABLE IF NOT EXISTS llm_calls(call_id TEXT PRIMARY KEY, ping_id TEXT, run_id TEXT, model TEXT, purpose TEXT, input_tokens INT, output_tokens INT, cache_key TEXT, cache_hit INT, ts TEXT);
CREATE TABLE IF NOT EXISTS effects(action_id TEXT PRIMARY KEY, effect_spec_json TEXT, observed_effect_json TEXT, matched INT, checked_at TEXT);
CREATE INDEX IF NOT EXISTS idx_receipts_consumed ON consumption_receipts(consumed_artifact_id, consumed_version);
CREATE INDEX IF NOT EXISTS idx_receipts_consumer ON consumption_receipts(consumer_artifact_id, consumer_version);
CREATE INDEX IF NOT EXISTS idx_pings_corr ON pings(correction_id, wave_id);
CREATE TRIGGER IF NOT EXISTS no_del_receipts BEFORE DELETE ON consumption_receipts BEGIN SELECT RAISE(ABORT,'append-only'); END;
CREATE TRIGGER IF NOT EXISTS no_del_pings BEFORE DELETE ON pings BEGIN SELECT RAISE(ABORT,'append-only'); END;
CREATE TRIGGER IF NOT EXISTS no_del_ping_responses BEFORE DELETE ON ping_responses BEGIN SELECT RAISE(ABORT,'append-only'); END;
CREATE TRIGGER IF NOT EXISTS upd_receipts BEFORE UPDATE ON consumption_receipts BEGIN SELECT RAISE(ABORT,'append-only'); END;
CREATE TRIGGER IF NOT EXISTS upd_ping_responses BEFORE UPDATE ON ping_responses BEGIN SELECT RAISE(ABORT,'append-only'); END;

-- ---------------------------------------------------------------- v3: the error review (SPEC.md v3). Same conventions: append-only.
CREATE TABLE IF NOT EXISTS gl_entries(entry_id TEXT PRIMARY KEY, txn_id TEXT, posted_at TEXT, eff_date TEXT, period TEXT, orig_period TEXT, entity TEXT,
  account TEXT, amount_cents INTEGER, memo TEXT, source_ref TEXT, import_id TEXT, correction_id TEXT, approval_id TEXT, world TEXT DEFAULT 'tidewall');
CREATE INDEX IF NOT EXISTS idx_gl_posted ON gl_entries(posted_at);
CREATE INDEX IF NOT EXISTS idx_gl_acct ON gl_entries(account, period);
CREATE TRIGGER IF NOT EXISTS no_del_gl BEFORE DELETE ON gl_entries BEGIN SELECT RAISE(ABORT,'append-only: corrections are new entries'); END;
CREATE TRIGGER IF NOT EXISTS no_upd_gl BEFORE UPDATE ON gl_entries BEGIN SELECT RAISE(ABORT,'append-only: corrections are new entries'); END;

CREATE TABLE IF NOT EXISTS kv(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS review_runs(run_id TEXT PRIMARY KEY, world TEXT, pinned_at TEXT, playbook_version TEXT, status TEXT, started_at TEXT, finished_at TEXT, summary_json TEXT);
CREATE TABLE IF NOT EXISTS recon_items(run_id TEXT, world TEXT, recon TEXT, outcome TEXT CHECK(outcome IN ('matched','cleared','exception')), reason TEXT,
  amount REAL, detail_json TEXT, exception_id TEXT);
CREATE TABLE IF NOT EXISTS exceptions(exception_id TEXT, run_id TEXT, world TEXT, recon TEXT, kind TEXT, title TEXT, amount REAL, system_of_record TEXT, trust_why TEXT,
  knowable_at TEXT, evidence_json TEXT, correction_json TEXT, detail_json TEXT, PRIMARY KEY(exception_id, run_id));
CREATE TABLE IF NOT EXISTS trace_items(item_id TEXT, run_id TEXT, world TEXT, file TEXT, locator TEXT, label TEXT, kind TEXT, value_num REAL, value_text TEXT, unit TEXT,
  tolerance REAL, display TEXT, owner TEXT, refs_json TEXT, PRIMARY KEY(item_id, run_id));
CREATE TABLE IF NOT EXISTS trace_links(item_id TEXT, run_id TEXT, status TEXT, metric_id TEXT, snapshot TEXT, method TEXT, confidence REAL, explanation TEXT,
  candidates_json TEXT, confirmed_by TEXT, confirmed_at TEXT, PRIMARY KEY(item_id, run_id));
CREATE TABLE IF NOT EXISTS ripples(ripple_id TEXT PRIMARY KEY, run_id TEXT, world TEXT, exception_id TEXT, created_at TEXT, counts_json TEXT, result_json TEXT);
CREATE TABLE IF NOT EXISTS evaluations(eval_id TEXT PRIMARY KEY, run_id TEXT, world TEXT, exception_id TEXT, playbook_version TEXT, claims_json TEXT, created_at TEXT, superseded_by TEXT);
CREATE TABLE IF NOT EXISTS jade_reviews(review_id TEXT PRIMARY KEY, eval_id TEXT, claim_key TEXT, verdict TEXT CHECK(verdict IN ('approve','overrule','escalate','flag')),
  agent_value_json TEXT, corrected_json TEXT, why TEXT, method TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS lessons(lesson_id TEXT PRIMARY KEY, world TEXT, mistake_kind TEXT, source TEXT, rule TEXT, evidence_json TEXT, enforcement TEXT,
  status TEXT, gate_json TEXT, proposed_at TEXT, decided_by TEXT, decided_at TEXT, playbook_version TEXT);
CREATE TABLE IF NOT EXISTS holds(hold_id TEXT PRIMARY KEY, world TEXT, target TEXT, reason TEXT, depends_on TEXT, state TEXT, created_at TEXT, released_at TEXT);
CREATE TABLE IF NOT EXISTS memos(memo_id TEXT, version INT, world TEXT, exception_id TEXT, markdown TEXT, created_at TEXT, PRIMARY KEY(memo_id, version));
CREATE VIEW IF NOT EXISTS audit_log AS SELECT event_id, ts, kind, actor, summary, detail_json, correction_id, run_id FROM events;
