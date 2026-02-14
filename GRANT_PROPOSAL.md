<h1>PRSpec: Continuous Specification Intelligence</h1>
<p><strong>Applicant:</strong> Safi El-Hassanine<br>
<strong>Project:</strong> PRSpec - Continuous Specification Intelligence<br>
<strong>Requested Funding:</strong> $35,000 <br>
<strong>Important Note: </strong>The requested grant can be reduced, or payments can be deferred until after each milestone is delivered, as proof of credibility, execution quality, and alignment with Ethereum’s vision and community service.<br>
<strong>Duration:</strong> 6 months<br>
<strong>RFP Reference:</strong> Ethereum Foundation ESP - Integrating LLMs into Ethereum Protocol Security Research</p>
<h2>Table of Contents</h2>
<ol>
<li><a href="#1-executive-summary">Executive Summary</a></li>
<li><a href="#2-background--motivation">Background & Motivation</a></li>
<li><a href="#3-technical-approach">Technical Approach</a></li>
<li><a href="#4-deliverables">Deliverables</a></li>
<li><a href="#5-project-plan--timeline">Project Plan & Timeline</a></li>
<li><a href="#6-budget-breakdown">Budget Breakdown</a></li>
<li><a href="#7-team-qualifications">Team Qualifications</a></li>
<li><a href="#8-success-metrics">Success Metrics</a></li>
<li><a href="#9-maintenance-plan">Maintenance Plan</a></li>
</ol>
<h2 id="1-executive-summary">1. Executive Summary</h2>
<p>Ethereum upgrades are accelerating—Dencun, Pectra, Fusaka—yet manual specification review remains the critical bottleneck. Security researchers currently spend hundreds of hours per upgrade reconciling <strong>consensus specs</strong> and <strong>execution specs</strong> against <strong>client implementations</strong>, often catching <strong>specification drift</strong> only after testnet deployment.</p>
<p><strong>PRSpec</strong> embeds LLM-powered compliance checks directly into CI pipelines. Unlike generic analysis tools, PRSpec understands <em>semantic intent</em>—distinguishing superficial refactoring from protocol-critical changes. It parses specifications, analyzes pull requests against canonical specs, and flags mismatches before code reaches testnet.</p>
<p>By integrating as a native GitHub Action, PRSpec brings specification alignment to client teams with minimal setup. The goal is not to replace human security researchers, but to handle the mechanical comparison work—catching specification drift at PR time rather than during audit phases, reducing review cycles by an estimated 40%.</p>
<h2 id="2-background--motivation">2. Background & Motivation</h2>
<h3>Personal Motivation</h3>
<p>As an engineer following Ethereum's development, I watched the Shanghai upgrade delays in 2023 with growing concern. Not from technical limitations, but from the sheer human coordination required to verify that five different <strong>client implementations</strong> correctly interpreted the withdrawal specifications. The <strong>consensus specs</strong> were clear to protocol researchers, yet subtle ambiguities led to weeks of cross-client reconciliation.</p>
<p>This experience crystallized a pattern across protocol upgrades: specification drift doesn’t come from negligence, but from cognitive overload. Security researchers are Ethereum’s scarcest resource; they shouldn’t spend hours on mechanical spec-to-code comparison.</p>
<h3>Problem Quantification</h3>
<p>Current manual review processes require approximately:</p>
<ul>
<li><strong>400-600 hours</strong> per major upgrade for spec reconciliation across <strong>client implementations</strong></li>
<li><strong>3-4 week</strong> feedback loops between spec finalization and compliance verification</li>
<li><strong>15-20%</strong> of security research time spent on mechanical comparison rather than deep analysis</li>
</ul>
<h3>Gap Analysis</h3>
<p>Existing tools address critical but distinct problems. Formal verification proves mathematical correctness but requires manual specification translation. Transaction analysis monitors runtime behavior but offers only post-hoc detection. Static analysis checks code quality but lacks semantic understanding of protocol specs. Fuzzing discovers edge cases but cannot verify spec alignment.</p>
<p><strong>PRSpec fills an unoccupied gap:</strong> automated specification↔code alignment with semantic understanding. It doesn’t compete with formal verification—it clears the manual bottleneck preventing researchers from focusing on formal methods.</p>
<h2 id="3-technical-approach">3. Technical Approach</h2>
<h3>Architecture Overview</h3>
<pre><code>┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Parser Layer  │────▶│  Analyzer (LLM)  │────▶│  Reporter Layer │
└─────────────────┘     └──────────────────┘     └─────────────────┘
        │                        │                        │
   ┌────┴────┐              ┌────┴────┐             ┌────┴────┐
   │EIP Specs│              │Semantic │             │GitHub   │
   │Consensus│              │Diff     │             │Action   │
   │Execution│              │Intent   │             │Dashboard│
   └─────────┘              │Analysis │             └─────────┘
                            └─────────┘</code></pre>
<p><strong>Parser Layer:</strong> Ingests <strong>consensus specs</strong> and <strong>execution specs</strong>, extracting machine-readable constraints from EIP specifications and markdown documentation.</p>
<p><strong>Analyzer (LLM):</strong> Core semantic engine performing intent analysis, constraint mapping, and drift detection using constrained prompting with structured output schemas.</p>
<p><strong>Reporter Layer:</strong> Native GitHub Action integration, web dashboard for security team oversight, and CLI interface for local development.</p>
<h3>How it works: Semantic Diff</h3>
<p>Traditional diff tools compare text; PRSpec compares <em>intent</em>. Our LLM analyzer:</p>
<ol>
<li>Extracts semantic constraints from specifications (e.g., "validator effective balance increments must be tracked per-epoch")</li>
<li>Maps constraints to code regions using AST analysis + LLM reasoning</li>
<li>Detects drift when code modifications violate extracted constraints, even if variable names change or structure refactors</li>
</ol>
<p>Example: A PR refactoring balance tracking might look harmless to text-diff but violate the epoch-boundary constraint extracted from <strong>consensus specs</strong>. PRSpec flags this as high-risk <strong>specification drift</strong> requiring human review.</p>
<h3>Security-First Design</h3>
<p><strong>Local LLM Option:</strong> For sensitive <strong>client implementations</strong>, PRSpec supports locally-hosted models (Llama 3, CodeLlama) via Ollama integration. No code leaves your infrastructure.</p>
<p><strong>Deterministic Analysis:</strong> We use constrained LLM prompting with JSON mode to ensure reproducible results. Same input → Same analysis output.</p>
<p><strong>Minimal Permissions:</strong> GitHub Action requires only read access to PR diffs and write access to PR comments—no repository code access beyond the diff being analyzed.</p>
<h3>Integration: Native GitHub Action</h3>
<pre><code>name: Specification Check
on: [pull_request]

jobs:
  prspec:
    runs-on: ubuntu-latest
    steps:
      - uses: prspec/action@v1
        with:
          specs: 'ethereum/consensus-specs'
          clients: 'geth,nethermind,lighthouse'</code></pre>
<p>Zero configuration for client teams. PRSpec automatically detects relevant EIP changes in the PR, cross-references against canonical specs, posts findings as PR comments with severity ratings, and updates the dashboard for security team oversight.</p>
<h3>Model Strategy</h3>
<p>We employ a tiered approach: GPT-4/Claude 3.5 for initial constraint extraction (high accuracy, complex reasoning), local 7B models for routine diff analysis (privacy, cost efficiency), and modular design allowing model swapping without architecture changes.</p>
<h2 id="4-deliverables">4. Deliverables</h2>
<h3>Hard Requirements</h3>
<table>
<tr><th>Requirement</th><th>Deliverable</th></tr>
<tr><td>Technical Architecture & Design</td><td>Comprehensive system architecture document with data flow diagrams</td></tr>
<tr><td>Working Prototype</td><td>Integration with Geth client, EIP-1559 specification compliance checking</td></tr>
<tr><td>Secure, Reproducible Operation</td><td>Local LLM support, deterministic prompting, containerized deployment</td></tr>
<tr><td>CI-Ready Interface</td><td>Production GitHub Action + CLI tool with PR integration</td></tr>
<tr><td>Documentation & Examples</td><td>Setup guides, API docs, example configurations for major clients</td></tr>
<tr><td>Secure Data Handling</td><td>Zero data retention, optional local-only processing, audit logs</td></tr>
</table>
<h3>Soft Requirements</h3>
<table>
<tr><th>Requirement</th><th>Approach</th></tr>
<tr><td>Modular Design</td><td>Pluggable LLM backends, swappable prompt templates, extensible spec parsers</td></tr>
<tr><td>Maintenance/Handoff</td><td>6-month transition plan to EF stewardship; Apache 2.0 licensing</td></tr>
<tr><td>Clear Milestones</td><td>Detailed timeline with measurable outputs per phase</td></tr>
</table>
<h2 id="5-project-plan--timeline">5. Project Plan & Timeline</h2>
<p><strong>Duration:</strong> 6 months (Feb 2026 – Aug 2026)</p>
<h3>Phase 1: Foundation (Months 1-2)</h3>
<p><strong>Goal:</strong> Expand prototype coverage, validate approach across multiple EIPs and clients</p>
<ul>
<li>Extend parser to handle 5 major EIPs (1559, 4844, 4788, 7002, 7251)</li>
<li>Integrate with 3 client codebases (Geth, Nethermind, Lighthouse)</li>
<li>Develop constraint extraction pipeline for <strong>consensus specs</strong> and <strong>execution specs</strong></li>
<li>Build initial test suite with known spec-code mismatches</li>
</ul>
<h3>Phase 2: Production (Months 3-4)</h3>
<p><strong>Goal:</strong> Ship production-ready GitHub Action, establish monitoring infrastructure</p>
<ul>
<li>Harden GitHub Action for public repository use</li>
<li>Build security dashboard for team-level oversight</li>
<li>Implement caching layer for spec embeddings</li>
<li>Conduct internal security audit</li>
<li>Pilot with 2+ client teams</li>
</ul>
<h3>Phase 3: Intelligence & Handoff (Months 5-6)</h3>
<p><strong>Goal:</strong> Auto-remediation suggestions, EF transition preparation</p>
<ul>
<li>Develop auto-remediation suggestions (human oversight required)</li>
<li>Create contribution guidelines and community documentation</li>
<li>Transition repository ownership to EF ecosystem</li>
<li>Establish long-term maintenance model</li>
</ul>
<h2 id="6-budget-breakdown">6. Budget Breakdown</h2>
<p><strong>Total Requested: $35,000</strong></p>
<table>
<tr><th>Category</th><th>Amount</th><th>Details</th></tr>
<tr><td>Development</td><td>$25,000</td><td>Safi El-Hassanine, full-time 6 months (engineering, architecture, implementation)</td></tr>
<tr><td>Infrastructure</td><td>$5,000</td><td>LLM API costs, testing infrastructure, GitHub Actions compute, local GPU rental</td></tr>
<tr><td>Security Audit</td><td>$3,000</td><td>Third-party security review of GitHub Action and data handling</td></tr>
<tr><td>Documentation/Community</td><td>$2,000</td><td>Technical writing, example repositories, workshop materials</td></tr>
</table>
<h2 id="7-team-qualifications">7. Team Qualifications</h2>
<p><strong>Safi El-Hassanine</strong> — Principal Engineer</p>
<p>I'm an Egyptian software engineer with 7+ years building production systems across fintech and distributed systems. My path to Ethereum protocol security wasn't academic—it was forged watching the coordination challenges of the Merge and subsequent upgrades, recognizing that our security bottlenecks are increasingly organizational rather than technical.</p>
<p><strong>Relevant Experience:</strong></p>
<ul>
<li>Built and scaled CI/CD pipelines processing 10M+ daily transactions</li>
<li>Developed static analysis tools for Solidity smart contracts (open source contributions)</li>
<li>Deep familiarity with Ethereum protocol specs through independent research and client codebase contributions</li>
<li>Experience with LLM application development (RAG systems, prompt engineering, local model deployment)</li>
</ul>
<p><strong>Why I’m a good fit:</strong></p>
<ol>
<li>Dual fluency in production engineering and protocol design</li>
<li>Experienced the pain of manual spec review through client discussions</li>
<li>Solo-founder approach means concentrated velocity with no coordination overhead</li>
<li>Deep belief that false confidence is worse than no confidence</li>
</ol>
<h2 id="8-success-metrics">8. Success Metrics</h2>
<table>
<tr><th>Metric</th><th>Target</th><th>Measurement Method</th></tr>
<tr><td>PRs Analyzed</td><td>200+ per month by month 6</td><td>GitHub Action telemetry (opt-in)</td></tr>
<tr><td>False Positive Rate</td><td>&lt;10%</td><td>Labeled dataset of historical spec-code mismatches</td></tr>
<tr><td>Client Adoption</td><td>2+ client teams in production</td><td>Integration confirmations from client maintainers</td></tr>
<tr><td>Time Savings</td><td>40% reduction in manual spec review</td><td>Time-tracking survey with pilot teams</td></tr>
<tr><td>Security Findings</td><td>5+ specification drift instances caught</td><td>Issue tracker analysis (public, anonymized)</td></tr>
</table>
<h2 id="9-maintenance-plan">9. Maintenance Plan</h2>
<p><strong>Open Source Commitment:</strong> All code released under Apache 2.0 license from day one.</p>
<p><strong>Phase 1 (Months 1-4):</strong> Active development under personal stewardship with weekly progress updates to EF ESP.</p>
<p><strong>Phase 2 (Months 5-6):</strong> Transition preparation—transfer repository to EF GitHub organization, onboard EF team to maintenance procedures, establish community governance model.</p>
<p><strong>Phase 3 (Post-grant):</strong> Community-driven maintenance with EF infrastructure hosting, client teams contributing adapters for new EIPs, and bug bounties for security-critical issues.</p>
<p><strong>Long-term Support:</strong> I commit to 12 months of advisory support post-grant (1-2 hours weekly) to ensure smooth knowledge transfer.</p>
<hr>
<p>Ethereum's security relies on careful reconciliation of specifications and implementations—a task perfectly suited for LLM augmentation, provided we build tools that understand protocol semantics rather than surface syntax.</p>
<p>PRSpec handles the mechanical, error-prone work of specification drift detection, letting human intelligence focus on the nuanced judgment calls that only experienced protocol engineers can make.</p>
<p>We're not replacing the security process. We're making it scale.</p>
<hr>
<p><strong>Contact Information:</strong><br>
Safi El-Hassanine<br>
Email: safi.elhassanine@example.com<br>
GitHub: github.com/safielhassanine<br>
Twitter/X: @safi_elhassanine</p>
<p><strong>Repository:</strong> github.com/safielhassanine/prspec</p>
