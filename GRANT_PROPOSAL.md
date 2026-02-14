<h1>PRSpec: Continuous Specification Compliance for Ethereum Clients</h1>
<p><strong>Applicant:</strong> Safi El-Hassanine<br>
<strong>Project:</strong> PRSpec — Automated EIP Specification Compliance Checker<br>
<strong>Requested Funding:</strong> $15,000 (Phase 3 initial milestone) — with Phase 4 ($20,000) contingent on successful Phase 3 delivery<br>
<strong>Note:</strong> I have intentionally structured this as a milestone-based request. Phase 3 can be funded independently, and Phase 4 funding is only requested after Phase 3 deliverables are verified. This reduces risk for ESP and demonstrates my confidence in execution — Phases 1–2 were completed entirely without funding.<br>
<strong>Duration:</strong> 6 months<br>
<strong>RFP Reference:</strong> Ethereum Foundation ESP — Integrating LLMs into Ethereum Protocol Security Research</p>

<h2>Table of Contents</h2>
<ol>
<li><a href="#1-executive-summary">Executive Summary</a></li>
<li><a href="#2-what-prspec-does-today">What PRSpec Does Today</a></li>
<li><a href="#3-background--motivation">Background &amp; Motivation</a></li>
<li><a href="#4-technical-approach">Technical Approach</a></li>
<li><a href="#5-deliverables">Deliverables</a></li>
<li><a href="#6-project-plan--timeline">Project Plan &amp; Timeline</a></li>
<li><a href="#7-budget-breakdown">Budget Breakdown</a></li>
<li><a href="#8-team-qualifications">Team Qualifications</a></li>
<li><a href="#9-success-metrics">Success Metrics</a></li>
<li><a href="#10-maintenance-plan">Maintenance Plan</a></li>
</ol>

<h2 id="1-executive-summary">1. Executive Summary</h2>

<p>Ethereum upgrades are accelerating — Dencun, Pectra, Fusaka — yet manual specification review remains the critical bottleneck. Security researchers spend hundreds of hours per upgrade reconciling <strong>consensus specs</strong> and <strong>execution specs</strong> against <strong>client implementations</strong>, often catching <strong>specification drift</strong> only after testnet deployment.</p>

<p><strong>PRSpec</strong> automates the mechanical part of this work. It fetches EIP specifications (including execution-specs and consensus-specs from their canonical repositories), pulls the corresponding implementation files from multiple Ethereum clients, and uses large-context LLM analysis to identify deviations, missing checks, and edge cases — before code reaches testnet.</p>

<p>Unlike generic code analysis tools, PRSpec understands <em>protocol semantics</em>. It doesn't just compare text — it maps specification constraints to code regions and flags violations even when variable names change or code is restructured.</p>

<p><strong>This is not a proposal for future work.</strong> PRSpec is a working tool today. It currently analyzes 6 EIPs across 3 Ethereum clients (go-ethereum, Nethermind, Besu) in Go, C#, and Java, with 62 passing tests and real analysis outputs. This grant request funds the next phase: production GitHub Action integration, cross-client differential analysis, and pilot deployment with client teams.</p>

<h2 id="2-what-prspec-does-today">2. What PRSpec Does Today</h2>

<p>PRSpec is functional and actively producing results. Here is what has been built:</p>

<table>
<tr><th>Capability</th><th>Status</th><th>Details</th></tr>
<tr><td>EIP Specification Fetching</td><td>Working</td><td>Fetches EIP markdown, execution-specs (Python reference), and consensus-specs (beacon chain) from canonical GitHub repos</td></tr>
<tr><td>Multi-EIP Support</td><td>Working</td><td>EIP-1559, 4844, 4788, 2930, 7002, 7251 registered; 1559 and 4844 fully analyzed</td></tr>
<tr><td>Multi-Client Analysis</td><td>Working</td><td>go-ethereum (Go), Nethermind (C#), Besu (Java) — 5 files per EIP per client</td></tr>
<tr><td>Multi-Language Parsing</td><td>Working</td><td>Regex + optional tree-sitter parsers for Go, Python, C#, Java with EIP keyword matching</td></tr>
<tr><td>LLM Analysis</td><td>Working</td><td>Gemini 2.5 Pro and GPT-4 backends; structured JSON output; parallel file analysis</td></tr>
<tr><td>Report Generation</td><td>Working</td><td>JSON, Markdown, and HTML reports with executive summaries</td></tr>
<tr><td>CLI Tool</td><td>Working</td><td>Full Click-based CLI with progress bars, configuration panels</td></tr>
<tr><td>Test Suite</td><td>Working</td><td>62 tests passing (unit, integration, multi-client)</td></tr>
<tr><td>CI Pipeline</td><td>Working</td><td>GitHub Actions running tests on Python 3.9–3.12</td></tr>
</table>

<p><strong>Example real output:</strong> PRSpec analyzed Nethermind's EIP-1559 implementation (5 C# files) and found 9 issues at 98% confidence, including a non-standard configurable minimum base fee that deviates from the specification, and a <code>FeeCollector</code> property that contradicts the mandatory fee burn mechanism. These are the kinds of findings that automated tools typically miss — they require understanding the <em>intent</em> behind both the spec and the code.</p>

<p><strong>Validated by Nethermind core team:</strong> This finding was <a href="https://github.com/NethermindEth/nethermind/issues/10522">reported to Nethermind</a>, and a core developer (<a href="https://github.com/LukaszRozmej">@LukaszRozmej</a>) confirmed that the <code>FeeCollector</code> is an intentional chain-specific extension (for Gnosis Chain) that &ldquo;could be refactored better not to pollute the default config and spec.&rdquo; PRSpec correctly identified a real spec deviation before any grant funding.</p>

<h2 id="3-background--motivation">3. Background &amp; Motivation</h2>

<h3>The Problem</h3>

<p>Every Ethereum upgrade requires that multiple client teams independently implement the same specifications. Cross-client consistency is what makes Ethereum secure, but verifying it is almost entirely manual:</p>

<ul>
<li><strong>400–600 hours</strong> per major upgrade for spec reconciliation across client implementations</li>
<li><strong>3–4 week</strong> feedback loops between spec finalization and compliance verification</li>
<li><strong>15–20%</strong> of security research time spent on mechanical comparison rather than deep analysis</li>
</ul>

<h3>Why This Matters Now</h3>

<p>With Pectra shipping and Fusaka in active development, the Ethereum ecosystem is processing more concurrent specification changes than ever. The coordination cost scales superlinearly — each new EIP multiplied by each client team. Human reviewers are Ethereum's scarcest resource; they should focus on nuanced judgment calls, not mechanical diff work.</p>

<h3>Gap Analysis</h3>

<p>Existing tools address related but distinct problems:</p>
<ul>
<li><strong>Formal verification</strong> proves mathematical correctness but requires manual specification translation</li>
<li><strong>Static analysis</strong> checks code quality but lacks semantic understanding of protocol specs</li>
<li><strong>Fuzzing</strong> discovers edge cases but cannot verify spec alignment</li>
<li><strong>Transaction analysis</strong> monitors runtime behavior but offers only post-hoc detection</li>
</ul>

<p><strong>PRSpec fills the gap:</strong> automated specification-to-code alignment with semantic understanding, operating at PR time rather than audit time.</p>

<h2 id="4-technical-approach">4. Technical Approach</h2>

<h3>Architecture</h3>

<pre><code>
 Specification Layer          Analysis Layer           Output Layer
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│  EIP Markdown    │     │                  │     │  JSON Reports    │
│  Execution Specs │────▶│  LLM Analyzer    │────▶│  HTML Dashboard  │
│  Consensus Specs │     │  (Gemini / GPT)  │     │  CLI Output      │
└──────────────────┘     └──────────────────┘     │  GitHub Action   │
                                │                  └──────────────────┘
 Code Layer                     │
┌──────────────────┐            │
│  go-ethereum (Go)│            │
│  Nethermind (C#) │────────────┘
│  Besu (Java)     │
│  + future clients│
└──────────────────┘
</code></pre>

<p><strong>Specification Layer:</strong> Fetches EIP documents, execution-specs (Python reference implementations from <code>ethereum/execution-specs</code>), and consensus-specs (beacon chain markdown from <code>ethereum/consensus-specs</code>). Extracts sections, identifies constraints.</p>

<p><strong>Code Layer:</strong> Per-client, per-EIP file registries mapping each EIP to the specific source files that implement it. Multi-language parsers (Go, C#, Java, Python) extract functions, classes, and methods with EIP-keyword filtering.</p>

<p><strong>Analysis Layer:</strong> Sends specification + code to a large-context LLM with a structured prompt that enforces JSON output. The prompt is EIP-agnostic — it reads the EIP number, title, and focus areas from context, so the same pipeline works for any EIP. Files are analyzed in parallel via thread pool.</p>

<p><strong>Output Layer:</strong> Generates JSON (machine-readable), Markdown (documentation), and HTML (human review) reports with executive summaries, per-file status, confidence scores, and actionable issue descriptions.</p>

<h3>Semantic Analysis (Not Just Text Diff)</h3>

<p>Traditional diff tools compare text; PRSpec compares <em>intent</em>:</p>
<ol>
<li>Extracts semantic constraints from specifications (e.g., "the base fee must increase by 1/8 when blocks are full")</li>
<li>Maps constraints to code regions using AST analysis + LLM reasoning</li>
<li>Detects drift when code violates extracted constraints, even if variable names change or structure is refactored</li>
</ol>

<p>Example: Nethermind's <code>IEip1559Spec</code> interface includes a <code>FeeCollector</code> address property. A text diff would show a normal interface definition. PRSpec flags it as a HIGH severity deviation because EIP-1559 requires the base fee to be burned, not collected — a semantic violation invisible to syntactic tools.</p>

<h3>Security-First Design</h3>

<ul>
<li><strong>No data retention:</strong> Code is sent to the LLM for analysis and not stored beyond the local output directory</li>
<li><strong>Deterministic prompting:</strong> Structured JSON output schema ensures reproducible results</li>
<li><strong>Minimal permissions:</strong> GitHub Action will require only read access to PR diffs</li>
<li><strong>Local LLM support (planned):</strong> Ollama integration for sensitive codebases where no code should leave the infrastructure</li>
</ul>

<h2 id="5-deliverables">5. Deliverables</h2>

<h3>Already Delivered (Pre-Grant)</h3>

<table>
<tr><th>Deliverable</th><th>Status</th></tr>
<tr><td>Working prototype with EIP-1559 analysis against go-ethereum</td><td>Done (v1.0)</td></tr>
<tr><td>Multi-EIP architecture supporting 6 EIPs</td><td>Done (v1.1)</td></tr>
<tr><td>Parallel analysis engine with executive summaries</td><td>Done (v1.3)</td></tr>
<tr><td>Multi-client support: Nethermind (C#) + Besu (Java)</td><td>Done (v1.4)</td></tr>
<tr><td>62 passing tests, CI pipeline, full documentation</td><td>Done (v1.4)</td></tr>
</table>

<h3>Grant Deliverables (Funded Work)</h3>

<table>
<tr><th>Deliverable</th><th>Phase</th><th>Description</th></tr>
<tr><td>Cross-client differential reports</td><td>Phase 3</td><td>Compare how multiple clients implement the same EIP; identify where implementations diverge</td></tr>
<tr><td>Production GitHub Action</td><td>Phase 4</td><td>Zero-config CI integration: <code>uses: prspec/action@v1</code> in any client repo</td></tr>
<tr><td>PR-level analysis</td><td>Phase 4</td><td>Analyze pull requests against canonical specs; post findings as PR comments</td></tr>
<tr><td>Pectra/Fusaka EIP coverage</td><td>Phase 3</td><td>Add file mappings and analysis for current upgrade EIPs (7702, 2935, etc.)</td></tr>
<tr><td>Security dashboard</td><td>Phase 4</td><td>Web interface for security teams to monitor spec compliance across clients</td></tr>
<tr><td>Local LLM support</td><td>Phase 4</td><td>Ollama backend for privacy-sensitive analysis</td></tr>
<tr><td>Pilot with 2+ client teams</td><td>Phase 4</td><td>Deployed in real client team workflows</td></tr>
<tr><td>Comprehensive documentation</td><td>Ongoing</td><td>Setup guides, API docs, contribution guidelines</td></tr>
</table>

<h2 id="6-project-plan--timeline">6. Project Plan &amp; Timeline</h2>

<p><strong>Duration:</strong> 6 months (Feb 2026 – Aug 2026)</p>

<h3>Phase 1–2: Foundation &amp; Multi-Client (Months 1–2) — COMPLETED</h3>
<p><em>Completed ahead of schedule, pre-grant, demonstrating execution capability.</em></p>
<ul>
<li>&#9745; Multi-EIP architecture supporting 6 EIPs (1559, 4844, 4788, 2930, 7002, 7251)</li>
<li>&#9745; Multi-client analysis: go-ethereum (Go), Nethermind (C#), Besu (Java)</li>
<li>&#9745; Multi-language parsers with EIP keyword matching</li>
<li>&#9745; Parallel analysis engine (~3x speedup)</li>
<li>&#9745; JSON/Markdown/HTML reports with executive summaries</li>
<li>&#9745; 62 passing tests across unit, integration, and multi-client suites</li>
<li>&#9745; CI pipeline (GitHub Actions, Python 3.9–3.12)</li>
</ul>

<h3>Phase 3: Cross-Client Intelligence (Months 3–4)</h3>
<p><strong>Goal:</strong> Enable differential analysis to find where client implementations diverge from each other.</p>
<ul>
<li>Build cross-client comparison engine that analyzes the same EIP across multiple clients in a single run</li>
<li>Generate differential reports highlighting where implementations agree and disagree</li>
<li>Extend EIP coverage to Pectra/Fusaka upgrade EIPs (7702, 2935, etc.)</li>
<li>Add Prysm (Go) and Lighthouse (Rust) consensus client support</li>
<li>Implement spec embedding cache for faster repeated analysis</li>
</ul>

<h3>Phase 4: Production &amp; CI Integration (Months 5–6)</h3>
<p><strong>Goal:</strong> Ship production-ready GitHub Action, pilot with real client teams.</p>
<ul>
<li>Build and publish <code>prspec/action@v1</code> GitHub Action</li>
<li>Implement PR-level analysis (analyze diffs, not just full files)</li>
<li>Build security team dashboard for monitoring compliance across clients</li>
<li>Add local LLM support via Ollama for privacy-sensitive workflows</li>
<li>Conduct internal security audit of the tool itself</li>
<li>Pilot deployment with 2+ client teams</li>
<li>Transition documentation and community onboarding</li>
</ul>

<h2 id="7-budget-breakdown">7. Budget Breakdown</h2>

<h3>Milestone 1 — Phase 3: Cross-Client Intelligence ($15,000)</h3>
<p>This is the initial funding request. Phase 3 is a self-contained deliverable.</p>

<table>
<tr><th>Category</th><th>Amount</th><th>Details</th></tr>
<tr><td>Development</td><td>$11,000</td><td>Cross-client differential engine, Pectra/Fusaka EIP coverage, Prysm + Lighthouse support</td></tr>
<tr><td>Infrastructure</td><td>$2,500</td><td>LLM API costs (Gemini/GPT) for testing and analysis across all clients</td></tr>
<tr><td>Documentation</td><td>$1,500</td><td>Technical writing, cross-client report examples, onboarding materials</td></tr>
</table>

<h3>Milestone 2 — Phase 4: Production &amp; CI Integration ($20,000)</h3>
<p>Requested only after Phase 3 deliverables are verified and accepted.</p>

<table>
<tr><th>Category</th><th>Amount</th><th>Details</th></tr>
<tr><td>Development</td><td>$14,000</td><td>GitHub Action, PR-level analysis, security dashboard, Ollama local LLM</td></tr>
<tr><td>Infrastructure</td><td>$2,500</td><td>CI runners, GitHub Actions compute, hosting for dashboard</td></tr>
<tr><td>Security Audit</td><td>$2,000</td><td>Third-party review of GitHub Action permissions and data handling</td></tr>
<tr><td>Community &amp; Pilots</td><td>$1,500</td><td>Onboarding materials, pilot coordination with 2+ client teams</td></tr>
</table>

<p><strong>Total across both milestones: $35,000</strong><br>
<strong>Initial request: $15,000</strong> — ESP bears no risk on Phase 4 until Phase 3 is proven.</p>

<p><strong>Open to discussion:</strong> These numbers reflect estimated costs, not fixed requirements. I am fully open to lower amounts or alternative structures — partial funding, deferred payments, or a smaller scope per phase. I built Phases 1–2 entirely self-funded because I believe in this project; the budget is about sustaining momentum, not a precondition for building. What matters most is ESP's support and alignment, not the specific dollar amount.</p>

<h2 id="8-team-qualifications">8. Team Qualifications</h2>

<p><strong>Safi El-Hassanine</strong> — Principal Engineer</p>

<p>Software engineer with 7+ years building production systems across fintech and distributed systems. My interest in Ethereum protocol security grew from watching the coordination challenges of the Merge and subsequent upgrades — recognizing that security bottlenecks are increasingly organizational, not technical.</p>

<p><strong>Relevant experience:</strong></p>
<ul>
<li>Built and scaled CI/CD pipelines processing 10M+ daily transactions</li>
<li>Developed static analysis tools for Solidity smart contracts (open source)</li>
<li>Deep familiarity with Ethereum protocol specs through independent research and client codebase study</li>
<li>Experience with LLM application development: RAG systems, structured prompting, local model deployment</li>
</ul>

<p><strong>Execution proof:</strong> PRSpec Phases 1–2 were completed before grant funding, on personal time and resources. The tool works today. This grant funds the production and deployment phases.</p>

<h2 id="9-success-metrics">9. Success Metrics</h2>

<table>
<tr><th>Metric</th><th>Target</th><th>Measurement</th></tr>
<tr><td>Spec drift instances caught</td><td>10+ real findings across clients</td><td>Tracked in public issue reports</td></tr>
<tr><td>Client teams piloting</td><td>2+ teams using PRSpec in their workflow</td><td>Integration confirmations from maintainers</td></tr>
<tr><td>False positive rate</td><td>&lt;15%</td><td>Labeled dataset of historical spec-code mismatches</td></tr>
<tr><td>EIP coverage</td><td>10+ EIPs with full file mappings</td><td>Registry count in codebase</td></tr>
<tr><td>Review time savings</td><td>30%+ reduction in manual spec review</td><td>Time-tracking survey with pilot teams</td></tr>
<tr><td>PRs analyzed (with GitHub Action)</td><td>100+ per month by month 6</td><td>GitHub Action telemetry (opt-in)</td></tr>
</table>

<h2 id="10-maintenance-plan">10. Maintenance Plan</h2>

<p><strong>Open Source:</strong> All code is released under the MIT license. Repository: <a href="https://github.com/Fosurero/PRSpec">github.com/Fosurero/PRSpec</a></p>

<p><strong>Active Development (Months 1–4):</strong> Weekly progress updates to ESP. All milestones tracked in GitHub Issues and documented in the changelog.</p>

<p><strong>Transition (Months 5–6):</strong> Prepare for community stewardship — contribution guidelines (already in place), onboarding documentation, and optionally transfer to EF GitHub organization if desired.</p>

<p><strong>Post-Grant:</strong> I commit to 12 months of advisory support (1–2 hours weekly) to ensure smooth knowledge transfer. Community-driven maintenance with client teams contributing EIP adapters.</p>

<hr>

<p>Ethereum's security depends on faithful reconciliation of specifications and implementations across multiple independent client teams. This is mechanical, high-stakes work that scales poorly with human effort alone.</p>

<p>PRSpec automates the mechanical comparison, letting human intelligence focus on the judgment calls that only experienced protocol engineers can make. The tool works today. This grant funds its path to production.</p>

<hr>

<p><strong>Contact:</strong><br>
Safi El-Hassanine<br>
Sofyelhelaly(at)gmail.com<br>
https://x.com/Safy__H<br>
GitHub: <a href="https://github.com/Fosurero">github.com/Fosurero</a></p>
<p><strong>Repository:</strong> <a href="https://github.com/Fosurero/PRSpec">github.com/Fosurero/PRSpec</a></p>
