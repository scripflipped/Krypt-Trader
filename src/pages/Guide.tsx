import {
  Activity, AlertTriangle, BarChart3, BookOpen, Briefcase, CheckCircle2,
  ExternalLink, Eye, FlaskConical, Gift, KeyRound, Layers, Sparkles, Target, Twitter, Zap,
} from 'lucide-react';
import { Card, Page, Section } from '../components/common';
import {
  KALSHI_DEMO_GUIDE, KALSHI_DEMO_SIGNUP, KALSHI_DEMO_URL, KALSHI_REFERRAL_URL,
} from '../utils/links';
import { followYuhgo, X_PROFILE } from '../utils/share';

export function GuidePage() {
  const open = (url: string) => () => void window.krypt.app.openExternal(url);

  return (
    <Page
      title="Guide"
      subtitle="How Krypt Trader works, what each setting does, and the trading edge it tries to capture."
    >
      <Card className="mb-6 border-krypt-purple/30 bg-gradient-to-br from-krypt-purple/15 via-krypt-glow/20 to-transparent">
        <div className="flex flex-col items-start gap-4 md:flex-row md:items-center">
          <div className="grid h-14 w-14 shrink-0 place-items-center rounded-2xl bg-krypt-glow shadow-krypt-strong">
            <Gift className="h-6 w-6 text-white" />
          </div>
          <div className="flex-1">
            <div className="text-sm font-semibold text-white">
              New to Kalshi? Claim $25 free with our referral.
            </div>
            <p className="mt-1 text-xs text-krypt-muted">
              Sign up via the Krypt referral link and Kalshi credits your account
              with $25 after your first deposit. Costs you nothing, supports the
              tool. Use it before connecting your API keys to maximize your starting
              bankroll.
            </p>
          </div>
          <div className="flex flex-col gap-2 shrink-0">
            <button onClick={open(KALSHI_REFERRAL_URL)} className="krypt-btn-primary">
              <Gift className="h-4 w-4" /> Claim $25 on Kalshi <ExternalLink className="h-3 w-3" />
            </button>
            <button
              onClick={() => void followYuhgo()}
              className="krypt-btn-default"
              title={`Open ${X_PROFILE} on X`}
            >
              <Twitter className="h-4 w-4" /> Follow {X_PROFILE} <ExternalLink className="h-3 w-3" />
            </button>
          </div>
        </div>
      </Card>

      <Section title="At a glance">
        <div className="grid gap-4 md:grid-cols-3">
          <FeatureCard
            icon={Eye}
            title="Two scanners"
            body="Whale tracker watches large taker fills (smart-money-style flow). Momentum tracker hunts price/volume divergences across active markets."
          />
          <FeatureCard
            icon={Target}
            title="Edge-based sizing"
            body="Position size scales linearly with the gap between signal confidence and the market's implied probability. Bigger edge → bigger bet, capped by your hard limits."
          />
          <FeatureCard
            icon={Layers}
            title="Risk gates everywhere"
            body="Per-market dedupe, per-event dedupe, max open positions, max daily new positions, exposure ceiling, daily stop-loss, and minimum cash reserve."
          />
        </div>
      </Section>

      <Section title="Setup in 5 minutes">
        <Card>
          <ol className="space-y-4 text-sm">
            <Step
              n={1}
              title="Sign up to Kalshi"
              body={
                <>
                  Use the referral link above for $25 free. Demo mode works without a
                  funded production account if you only want to test on demo.
                </>
              }
            />
            <Step
              n={2}
              title="Generate API credentials on Kalshi"
              body={
                <>
                  Kalshi → <span className="text-white">Account → API Keys → New Key</span>.
                  Save the API key ID and download the RSA private key file (it's a
                  one-time download). For demo, do this on{' '}
                  <button
                    onClick={open('https://demo.kalshi.co')}
                    className="text-krypt-purple hover:underline"
                  >demo.kalshi.co</button>.
                </>
              }
            />
            <Step
              n={3}
              title="Paste them on the API Keys page"
              body={
                <>
                  Click <KeyRound className="inline h-3.5 w-3.5" /> API Keys in the
                  sidebar, paste the key ID, paste the RSA PEM block, hit{' '}
                  <span className="text-white">Save &amp; Verify</span>. The bot
                  authenticates with Kalshi and starts streaming your balance.
                </>
              }
            />
            <Step
              n={4}
              title="Pick a strategy preset"
              body={
                <>
                  <Sparkles className="inline h-3.5 w-3.5" /> Strategies offers
                  Conservative, Balanced, and High-Risk presets. They tweak edge
                  thresholds, position sizing, and which scanners are enabled. You
                  can clone one into <Briefcase className="inline h-3.5 w-3.5" /> Profiles
                  and tune any field.
                </>
              }
            />
            <Step
              n={5}
              title="Test on demo, then go live"
              body={
                <>
                  Run on the <span className="text-white">Demo</span> environment
                  (Settings) until you've watched a few scan cycles and trust the
                  config, then switch to Production to trade real money. The Pause
                  button at the top right is your kill-switch.
                </>
              }
            />
          </ol>
        </Card>
      </Section>

      <Section title="Test free on Kalshi's demo exchange">
        <Card className="border-krypt-win/25 bg-krypt-win/[0.03]">
          <div className="mb-4 flex items-start gap-3">
            <div className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-krypt-win/15 text-krypt-win">
              <FlaskConical className="h-5 w-5" />
            </div>
            <p className="text-sm text-krypt-muted">
              Kalshi runs a full <span className="text-white">demo exchange</span> with real order
              matching, fills, and settlement — but <span className="text-white">play money</span>.
              It's the most realistic way to test a strategy with zero risk: connect demo keys, enable
              auto-trading, and the bot places real orders against the sandbox — play money, no risk.
            </p>
          </div>
          <ol className="space-y-4 text-sm">
            <Step n={1} title="Create a demo account" body={
              <>Go to{' '}
                <button onClick={open(KALSHI_DEMO_SIGNUP)} className="text-krypt-purple hover:underline">demo.kalshi.co/sign-up</button>
                {' '}and sign up with mock info (fake name, address, SSN — no real details), a real
                email, and a password. <span className="text-white">The domain is .co, not .com.</span>
              </>
            } />
            <Step n={2} title="Add play money" body={
              <>Deposit with a test card — Visa <span className="font-mono text-white">4000 0566 5566 5556</span>{' '}
                or Mastercard <span className="font-mono text-white">5200 8282 8282 8210</span>, any future
                expiry and any CVV. It's all sandbox; no real money moves.
              </>
            } />
            <Step n={3} title="Generate demo API keys" body={
              <>On{' '}
                <button onClick={open(KALSHI_DEMO_URL)} className="text-krypt-purple hover:underline">demo.kalshi.co</button>
                {' '}→ Account → API Keys → New Key. Save the key ID and download the RSA private key.
                Demo keys are completely separate from production.
              </>
            } />
            <Step n={4} title="Connect them here (Demo env)" body={
              <>Open <KeyRound className="inline h-3.5 w-3.5" /> API Keys, set the environment to{' '}
                <span className="text-white">Demo</span>, paste the key ID + RSA PEM, and hit Save &amp; Verify.
              </>
            } />
            <Step n={5} title="Run it for real — on the sandbox" body={
              <>Pick a strategy, turn <span className="text-white">dry-run off</span> and enable trading.
                The bot now fires live orders with fake money. Let it rack up a few hundred resolved
                trades, then judge it on the <span className="text-white">History</span> page (and the
                backtested-edge chips on the Strategies page).
              </>
            } />
          </ol>
          <div className="mt-4 flex flex-wrap gap-2">
            <button onClick={open(KALSHI_DEMO_SIGNUP)} className="krypt-btn-primary">
              <FlaskConical className="h-4 w-4" /> Open demo.kalshi.co <ExternalLink className="h-3 w-3" />
            </button>
            <button onClick={open(KALSHI_DEMO_GUIDE)} className="krypt-btn-default">
              Full Kalshi demo guide <ExternalLink className="h-3 w-3" />
            </button>
          </div>
          <div className="mt-3 text-[11px] text-krypt-dim">
            Demo and production are fully separate (separate logins, keys, and funds). Never send real
            crypto to demo wallet addresses.
          </div>
        </Card>
      </Section>

      <Section title="How a trade flows">
        <Card>
          <FlowDiagram />
          <div className="mt-4 grid gap-3 text-xs text-krypt-muted md:grid-cols-3">
            <div>
              <div className="text-[11px] uppercase tracking-wider text-white">
                1. Scan
              </div>
              Whale tracker hits Kalshi every {`~`}2 min looking for taker fills above
              your dollar threshold. Momentum tracker scans markets every {`~`}90s for
              moves that match your signal types. Both write rows into the local DB.
            </div>
            <div>
              <div className="text-[11px] uppercase tracking-wider text-white">
                2. Filter &amp; size
              </div>
              Trader checks confidence, edge, allowed categories, dedup, exposure
              caps, and daily risk gates. If a candidate passes, sizing maps the
              edge in pts to a $ stake between your min and max fractions.
            </div>
            <div>
              <div className="text-[11px] uppercase tracking-wider text-white">
                3. Place &amp; track
              </div>
              Order goes in as a limit cross (or mid, depending on order style).
              Polled every 30s for fill status. On settlement, the resolver reads
              the market's binary outcome and writes the final P&amp;L.
            </div>
          </div>
        </Card>
      </Section>

      <Section title="Setting cheat sheet">
        <Card>
          <div className="grid gap-x-8 gap-y-3 md:grid-cols-2">
            <SettingRow
              label="min_confidence_*"
              hint="The signal's quality score (0–100). Higher = more selective. Conservative ≈ 78, Balanced ≈ 70, High-Risk ≈ 60."
            />
            <SettingRow
              label="min_edge_pts_*"
              hint="Required gap between confidence and the market's implied probability. 5 pts = a small edge, 12+ pts = strong."
            />
            <SettingRow
              label="min/max_size_fraction"
              hint="Fraction of bankroll bet at minimum / maximum edge. Sizing interpolates between them. Cap with hard_max_position_usd."
            />
            <SettingRow
              label="max_open_positions"
              hint="Hard ceiling on simultaneous unsettled bets. Protects against signal storms."
            />
            <SettingRow
              label="max_total_exposure_fraction"
              hint="At-risk capital cannot exceed this fraction of bankroll. Shrinks new bets when full."
            />
            <SettingRow
              label="stop_loss_on_day"
              hint="Negative dollar amount. If today's realized P&L hits this, no new entries until tomorrow."
            />
            <SettingRow
              label="take_profit_on_day"
              hint="Positive dollar amount. Same idea — locks in a profitable day."
            />
            <SettingRow
              label="order_style"
              hint="limit_cross (aggressive: cross spread to fill fast), limit_mid (cheaper, may not fill), or market."
            />
            <SettingRow
              label="allowed_categories"
              hint="Toggle market categories on/off (Sports, Politics, Crypto, etc.). Empty = trade nothing."
            />
            <SettingRow
              label="min_cash_reserve_fraction"
              hint="Always keep at least this fraction of bankroll in cash. Prevents over-leveraging."
            />
          </div>
        </Card>
      </Section>

      <Section title="Reading the dashboard">
        <Card>
          <ul className="space-y-2 text-sm text-krypt-muted">
            <Row
              icon={BarChart3}
              label="Total Balance"
              body="Cash + portfolio (live mark-to-market). Updated from Kalshi every snapshot."
            />
            <Row
              icon={Target}
              label="ROI"
              body="(Total - bankroll baseline) / baseline. Baseline is your manual start_bankroll_usd, or auto-detected from your first snapshot."
            />
            <Row
              icon={CheckCircle2}
              label="Today P&L"
              body="Sum of realized P&L on positions resolved today (rolls over at midnight). Does not include unrealized swing on still-open bets."
            />
            <Row
              icon={Briefcase}
              label="Open Positions"
              body="Count of filled / partial bets that haven't settled yet. The cap is max_open_positions."
            />
            <Row
              icon={Activity}
              label="Recent resolutions"
              body="The latest settled bets with their P&L. Pair this with the Positions page's Won / Lost tabs to see the whole story."
            />
          </ul>
        </Card>
      </Section>

      <Section title="When P&amp;L looks weird">
        <Card>
          <div className="mb-3 flex items-start gap-3 rounded-lg border border-krypt-warn/30 bg-krypt-warn/5 p-3">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-krypt-warn" />
            <div className="text-xs text-krypt-muted">
              <span className="text-white">Today P&L can be negative while your balance climbs.</span>
              {' '}Realized P&L only counts <span className="text-white">settled</span> bets.
              If your open positions are appreciating, your total balance goes up
              even though "Today P&L" reflects only the bets that already
              resolved. That's normal — wait for settlement.
            </div>
          </div>
          <div className="text-sm text-krypt-muted">
            If something looks broken (wrong wins/losses, stuck positions, etc.):
          </div>
          <ul className="mt-2 space-y-1.5 text-sm text-krypt-muted">
            <li>
              <span className="text-white">Positions → Reconcile</span> — re-syncs
              local rows with Kalshi's live position list.
            </li>
            <li>
              <span className="text-white">Positions → Resolve Now</span> — forces
              one resolution pass for any settled markets.
            </li>
            <li>
              <span className="text-white">Positions → Recompute P&amp;L</span> —
              wipes locally-stored P&L for resolved trades and rebuilds from each
              market's settlement value. Use after upgrading or if the dashboard
              shows obviously wrong wins/losses.
            </li>
            <li>
              <span className="text-white">Restart</span> button (top bar) — bounces
              the Python backend if it's stuck.
            </li>
          </ul>
        </Card>
      </Section>

      <Section title="Strategy intuition">
        <Card>
          <div className="grid gap-4 md:grid-cols-3">
            <StratBlock
              icon={Zap}
              tone="loss"
              title="High Risk"
              body="Lower confidence floor (~60), wider edge tolerance, higher max size fraction. Lots of fills, lots of swings, biggest variance. Best for finding what works fast on demo."
            />
            <StratBlock
              icon={Activity}
              tone="purple"
              title="Balanced"
              body="Default. Confidence ~70, edge ≥ 5pts, sizing 1.5–6% of bankroll. Mix of whale and momentum signals. Reasonable variance, plenty of trades to evaluate."
            />
            <StratBlock
              icon={CheckCircle2}
              tone="win"
              title="Conservative"
              body="Confidence ≥ 78, edge ≥ 8pts, smaller sizing, tight per-event dedupe. Fewer trades but higher hit-rate. Best when you want to ride out long stretches."
            />
          </div>
          <div className="mt-4 text-xs text-krypt-dim">
            All three are starting points — clone any of them into a Profile and
            adjust. Track outcomes via the History page over a few days before you
            commit real capital.
          </div>
        </Card>
      </Section>

      <Section title="Tips">
        <Card>
          <ul className="space-y-2 text-sm text-krypt-muted">
            <li>
              <BookOpen className="mr-2 inline h-3.5 w-3.5" />
              Run the bot on demo for at least a few hundred resolved trades before
              flipping to production. The Profiles page lets you A/B test settings.
            </li>
            <li>
              <BookOpen className="mr-2 inline h-3.5 w-3.5" />
              Tighten <span className="text-white">allowed_categories</span> if you
              don't trust certain markets (e.g., low-liquidity regional sports).
            </li>
            <li>
              <BookOpen className="mr-2 inline h-3.5 w-3.5" />
              Use <span className="text-white">order_expiration_sec</span> to cancel
              resting orders that haven't filled. Stale fills at bad prices kill edge.
            </li>
            <li>
              <BookOpen className="mr-2 inline h-3.5 w-3.5" />
              The History page's Daily P&L chart is the truest signal of whether
              your config has edge. Don't judge from a single trade.
            </li>
          </ul>
        </Card>
      </Section>
    </Page>
  );
}


function FeatureCard({
  icon: Icon, title, body,
}: { icon: React.ComponentType<{ className?: string }>; title: string; body: string }) {
  return (
    <Card>
      <div className="flex items-center gap-2">
        <div className="grid h-8 w-8 place-items-center rounded-lg bg-krypt-purple/15 text-krypt-purple">
          <Icon className="h-4 w-4" />
        </div>
        <div className="text-sm font-semibold text-white">{title}</div>
      </div>
      <p className="mt-3 text-xs leading-relaxed text-krypt-muted">{body}</p>
    </Card>
  );
}

function Step({
  n, title, body,
}: { n: number; title: string; body: React.ReactNode }) {
  return (
    <li className="flex items-start gap-3">
      <div className="grid h-7 w-7 shrink-0 place-items-center rounded-full border border-krypt-purple/40 bg-krypt-purple/10 text-xs font-semibold text-krypt-purple">
        {n}
      </div>
      <div>
        <div className="text-sm font-medium text-white">{title}</div>
        <p className="mt-0.5 text-xs leading-relaxed text-krypt-muted">{body}</p>
      </div>
    </li>
  );
}

function SettingRow({ label, hint }: { label: string; hint: string }) {
  return (
    <div>
      <div className="font-mono text-[11px] text-krypt-purple">{label}</div>
      <div className="mt-0.5 text-xs leading-relaxed text-krypt-muted">{hint}</div>
    </div>
  );
}

function Row({
  icon: Icon, label, body,
}: { icon: React.ComponentType<{ className?: string }>; label: string; body: string }) {
  return (
    <li className="flex items-start gap-3">
      <Icon className="mt-0.5 h-4 w-4 shrink-0 text-krypt-purple" />
      <div className="text-xs">
        <span className="text-white">{label}</span>
        <span className="ml-2 text-krypt-muted">{body}</span>
      </div>
    </li>
  );
}

function StratBlock({
  icon: Icon, tone, title, body,
}: {
  icon: React.ComponentType<{ className?: string }>;
  tone: 'win' | 'loss' | 'purple';
  title: string;
  body: string;
}) {
  const toneClasses = {
    win: 'border-krypt-win/30 bg-krypt-win/5 text-krypt-win',
    loss: 'border-krypt-loss/30 bg-krypt-loss/5 text-krypt-loss',
    purple: 'border-krypt-purple/30 bg-krypt-purple/5 text-krypt-purple',
  }[tone];
  return (
    <div className={`rounded-xl border p-4 ${toneClasses}`}>
      <div className="flex items-center gap-2">
        <Icon className="h-4 w-4" />
        <div className="text-sm font-semibold">{title}</div>
      </div>
      <p className="mt-2 text-xs leading-relaxed text-krypt-muted">{body}</p>
    </div>
  );
}

function FlowDiagram() {
  return (
    <svg viewBox="0 0 720 130" className="w-full text-krypt-muted">
      {[
        { x: 20, label: 'Kalshi API', sub: 'markets · fills' },
        { x: 175, label: 'Scanner', sub: 'whale + momentum' },
        { x: 330, label: 'Trader', sub: 'filter · size · place' },
        { x: 485, label: 'Order book', sub: 'limit cross' },
        { x: 620, label: 'Resolver', sub: 'settlement P&L' },
      ].map((n, i) => (
        <g key={i}>
          <rect
            x={n.x} y={35} width={90} height={60} rx={10}
            className="fill-krypt-surface2 stroke-krypt-border" strokeWidth={1}
          />
          <text x={n.x + 45} y={62} textAnchor="middle" className="fill-white text-[11px] font-semibold">
            {n.label}
          </text>
          <text x={n.x + 45} y={78} textAnchor="middle" className="fill-krypt-muted text-[10px]">
            {n.sub}
          </text>
        </g>
      ))}
      {[110, 265, 420, 575].map((x, i) => (
        <g key={i}>
          <line x1={x} y1={65} x2={x + 65} y2={65} stroke="currentColor" strokeWidth={1.5} markerEnd="url(#arrow)" />
        </g>
      ))}
      <defs>
        <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto">
          <path d="M0,0 L10,5 L0,10 z" fill="currentColor" />
        </marker>
      </defs>
    </svg>
  );
}
