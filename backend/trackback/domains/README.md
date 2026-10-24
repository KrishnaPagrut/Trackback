The core (`trackback/core/`) is domain-agnostic: versions, artifacts, receipts, waves, pings, Memento, the LLM gateway, approvals and replay. It never imports a domain.
`trackback/domains/finance/` is one implementation of `core/domain.py`'s `DomainPack`: materiality, period locks, estimate-vs-error, "not affected" reasons, the compensation catalog, approver roles, tie-outs and the norms miner.
