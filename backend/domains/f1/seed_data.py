"""
F1 domain seed data: base knowledge facts and mock news events.
"""
from datetime import datetime, timedelta

# ── Seed knowledge facts (tier_visibility=3 = visible to all tiers) ──────────
SEED_FACTS = [
    {
        "title": "DRS Effect on Following Distance",
        "content": (
            "The Drag Reduction System (DRS) opens the rear wing flap when a car is within "
            "1 second of the car ahead at a designated detection point. This reduces drag by "
            "roughly 10–12%, adding approximately 10–15 km/h of top speed on straights. "
            "Since 2022 ground-effect regulations, DRS dependency has reduced slightly as "
            "cars can follow more closely without losing significant downforce."
        ),
        "confidence": 0.98,
    },
    {
        "title": "Undercut vs Overcut Strategy",
        "content": (
            "An undercut involves pitting earlier than a rival to benefit from fresh tyre "
            "pace and track position after the rival pits. An overcut involves staying out "
            "longer to benefit from track position and a clear lap while rivals are on slower "
            "out-laps. The undercut is generally more reliable; the overcut requires sufficient "
            "pace on older tyres and low traffic risk."
        ),
        "confidence": 0.97,
    },
    {
        "title": "2022 Regulation Reset — Ground Effect Return",
        "content": (
            "From 2022, F1 regulations mandated a return to ground-effect aerodynamics with "
            "venturi tunnels under the floor, replacing the previous downwash-dominated concept. "
            "This was intended to allow cars to follow more closely (+40% closer following). "
            "Red Bull Racing achieved the best correlation from 2022 onwards, winning back-to-back "
            "Constructors Championships in 2022 and 2023."
        ),
        "confidence": 0.99,
    },
    {
        "title": "Pirelli Tyre Compound Hierarchy",
        "content": (
            "Pirelli supplies F1 with five dry compounds: C1 (hardest) through C5 (softest). "
            "Races use three adjacent compounds labelled Hard (white), Medium (yellow), Soft (red). "
            "Selection varies by circuit — Monaco uses C3/C4/C5 while Monza uses C1/C2/C3. "
            "Mandatory two-compound rule requires at least two different compounds per race "
            "for cars not starting on wet/intermediate tyres."
        ),
        "confidence": 0.97,
    },
    {
        "title": "Safety Car & Virtual Safety Car Windows",
        "content": (
            "Safety Car (SC) deployments create free pitstop windows as lap times artificially "
            "inflate. Teams with an upcoming stop should pit immediately under SC. VSC deployments "
            "are shorter but add roughly 35–40 seconds to lap times. The VSC window benefit "
            "decreases the earlier in the stint the car is — teams must calculate whether the "
            "delta to a fresh tyre outweighs track position loss."
        ),
        "confidence": 0.95,
    },
    {
        "title": "Hamilton's Move to Ferrari — 2025",
        "content": (
            "Lewis Hamilton, 7-time World Champion, left Mercedes after 11 seasons to join "
            "Scuderia Ferrari for the 2025 season. Hamilton partnered Charles Leclerc. "
            "This ended a 30+ year wait for Hamilton who grew up idolizing Ferrari and Ayrton Senna. "
            "His Mercedes replacement was Kimi Antonelli."
        ),
        "confidence": 0.99,
    },
    {
        "title": "2026 Regulations — Power Unit Overhaul",
        "content": (
            "From 2026, F1's power unit regulations change significantly: the MGU-H is removed, "
            "the electrical component increases to ~50% of total power, and the V6 internal "
            "combustion engine produces around 400kW. New entrants: Audi (via Sauber) and Ford "
            "(supporting Red Bull). The aerodynamic regulations also change substantially to "
            "compensate for the different power unit characteristics."
        ),
        "confidence": 0.96,
    },
    {
        "title": "Red Bull Dominance 2021–2023",
        "content": (
            "Red Bull Racing, under designer Adrian Newey, dominated F1 from 2021–2023. "
            "Max Verstappen won consecutive World Championships in 2021, 2022, and 2023. "
            "The 2023 season saw Red Bull win 21 of 22 races — the most dominant season in "
            "F1 history. The RB19 achieved exceptional low-speed and high-speed performance "
            "through superior floor concept and DRS efficiency."
        ),
        "confidence": 0.99,
    },
    {
        "title": "McLaren 2024 Resurgence",
        "content": (
            "McLaren achieved a dramatic performance step between 2023 and 2024 seasons. "
            "Lando Norris won multiple races in 2024 and contended for the championship. "
            "The MCL38 was particularly strong in medium-to-high-speed corners. "
            "McLaren's upgrade at the 2023 British GP is widely regarded as the turning point "
            "that began their Constructors Championship challenge."
        ),
        "confidence": 0.97,
    },
    {
        "title": "Porpoising Phenomenon in 2022",
        "content": (
            "The return of ground-effect aerodynamics in 2022 introduced porpoising — "
            "an oscillation where cars bounce rhythmically at high speed as the floor stalls "
            "and re-attaches aerodynamic suction repeatedly. Teams most affected included "
            "Mercedes and Ferrari. Red Bull managed the issue better through superior floor "
            "geometry. The FIA introduced new TD039 technical directive mid-season to limit "
            "vertical oscillation."
        ),
        "confidence": 0.98,
    },
    {
        "title": "F1 Sprint Race Format",
        "content": (
            "F1 Sprint events feature a compressed weekend format: FP1 followed by Sprint "
            "Qualifying (SQ1/SQ2/SQ3), then the Sprint race (~100km), then main qualifying "
            "and the Grand Prix. Sprint grids are set by sprint qualifying, not main qualifying. "
            "Sprint results set race grid only at select events. Points awarded to top 8 Sprint "
            "finishers (8-7-6-5-4-3-2-1). Approximately 6 sprint events per season."
        ),
        "confidence": 0.96,
    },
    {
        "title": "Fastest Lap Point Rule",
        "content": (
            "A bonus championship point is awarded for the fastest lap of the race, provided "
            "the driver finishing fastest is also classified in the top 10. This rule, introduced "
            "in 2019, creates late-race strategic complexity — teams may pit a top-10 runner for "
            "fresh tyres to attempt the fastest lap even when it costs positions."
        ),
        "confidence": 0.98,
    },
]


# ── Mock F1 news events (spanning a full 2025 season) ────────────────────────
def make_dt(days_ago: int) -> datetime:
    return datetime.utcnow() - timedelta(days=days_ago)


SEED_NEWS = [
    # Pre-season
    {
        "headline": "Ferrari unveils SF-25 with radical sidepod-less concept",
        "content": (
            "Scuderia Ferrari has shocked the paddock by revealing the SF-25 features an "
            "extremely aggressive sidepod undercut inspired by 2022 Red Bull concepts. "
            "Lewis Hamilton's first car in red appears significantly different from the "
            "2024 car. Technical director Loic Serra says the concept targets 2026 readiness."
        ),
        "event_type": "technical",
        "published_at": make_dt(120),
    },
    {
        "headline": "Red Bull's RB21 passes all crash tests — Adrian Newey's final design",
        "content": (
            "The RB21 has completed homologation. Sources suggest it is Adrian Newey's final "
            "complete design before his departure to Aston Martin. The car shows evolutionary "
            "development from the championship-winning RB19 philosophy."
        ),
        "event_type": "technical",
        "published_at": make_dt(115),
    },
    {
        "headline": "McLaren confirms major floor concept revision for 2025",
        "content": (
            "McLaren's MCL39 features a significantly revised floor compared to the MCL38. "
            "The team's new wind tunnel data suggests improved high-speed downforce. "
            "Lando Norris says 'the car feels different — more planted.' "
            "Zak Brown calls 2025 'our championship year.'"
        ),
        "event_type": "technical",
        "published_at": make_dt(110),
    },
    # Bahrain GP
    {
        "headline": "Verstappen wins Bahrain opener, Ferrari struggles with overheating",
        "content": (
            "Max Verstappen converted pole to victory in Bahrain. Ferrari's SF-25 showed "
            "strong qualifying pace but suffered unexpected rear tyre overheating in race "
            "conditions, dropping Hamilton from P3 to P7. McLaren's Norris finished second."
        ),
        "event_type": "race_result",
        "published_at": make_dt(90),
    },
    # Saudi Arabian GP
    {
        "headline": "Hamilton takes maiden Ferrari win in Jeddah thriller",
        "content": (
            "Lewis Hamilton scored his first victory in Ferrari colours at the Saudi Arabian GP "
            "after a strategic masterclass. Ferrari deployed the undercut perfectly under VSC, "
            "vaulting Hamilton from P4 to the lead. Leclerc finished third. "
            "The crowd gave Hamilton a standing ovation."
        ),
        "event_type": "race_result",
        "published_at": make_dt(77),
    },
    # Australian GP
    {
        "headline": "Norris wins Melbourne as Red Bull suffer double DNF",
        "content": (
            "Lando Norris took a dominant victory in Melbourne as both Red Bull cars retired "
            "with hydraulic failures. Verstappen led until lap 34 before parking. "
            "McLaren now lead the Constructors Championship by 18 points."
        ),
        "event_type": "race_result",
        "published_at": make_dt(63),
    },
    # Technical development
    {
        "headline": "FIA clarifies floor flex rules — Red Bull and McLaren forced to modify",
        "content": (
            "Following protests about floor flexibility, the FIA has issued Technical Directive "
            "TD018/25 tightening load deflection tests. Red Bull and McLaren are primarily "
            "affected, estimated to cost 0.15–0.20 seconds per lap. Ferrari and Mercedes "
            "confirmed compliant."
        ),
        "event_type": "regulation",
        "published_at": make_dt(55),
    },
    # Spanish GP
    {
        "headline": "Leclerc masters Barcelona to give Ferrari Constructors lead",
        "content": (
            "Charles Leclerc drove an imperious race in Spain to take victory from pole. "
            "The SF-25's aerodynamic efficiency proved decisive on Barcelona's high-speed "
            "sections. Ferrari now lead the Constructors Championship with 185 points. "
            "Verstappen finished fourth after a late puncture."
        ),
        "event_type": "race_result",
        "published_at": make_dt(42),
    },
    # Monaco GP
    {
        "headline": "Monaco GP: Leclerc wins at home, Hamilton controversially penalised",
        "content": (
            "Charles Leclerc won his home race in Monaco for the second time. Hamilton finished "
            "second on the road but received a 5-second penalty for an unsafe release, dropping "
            "to fourth. Ferrari strategy called — bringing Hamilton in one lap early. "
            "Norris inherited second from Hamilton after the penalty."
        ),
        "event_type": "race_result",
        "published_at": make_dt(28),
    },
    # Transfer
    {
        "headline": "Adrian Newey's Aston Martin car concept leaked — radical vacuum floor",
        "content": (
            "Images allegedly showing the Aston Martin AMR27 concept — Newey's first car for "
            "the team — have appeared online. The concept appears to feature an extreme "
            "interpretation of the 2026 regulations' aerodynamic rules, with a very low "
            "nose and radical underfloor channelling."
        ),
        "event_type": "technical",
        "published_at": make_dt(14),
    },
    # Canadian GP (upcoming)
    {
        "headline": "Canadian GP preview: Street circuit specialists tipped — Norris seeks title gap",
        "content": (
            "With the Canadian Grand Prix approaching, McLaren's Lando Norris arrives trailing "
            "Ferrari's Charles Leclerc by 8 points in the Drivers Championship. Montreal's "
            "stop-start circuit should suit cars with strong traction and braking stability. "
            "Rain is forecast for Saturday qualifying."
        ),
        "event_type": "race_result",
        "published_at": make_dt(3),
    },
    # Apex Award predictions context
    {
        "headline": "Season analysis: Five key questions for the 2025 F1 championship run-in",
        "content": (
            "1. Can Ferrari sustain their aerodynamic advantage after the floor directive? "
            "2. Will Verstappen's RB21 find the pace on street circuits? "
            "3. Is Hamilton's Monaco penalty a sign of tension with Ferrari strategy? "
            "4. Can Norris close on Leclerc in the Drivers standings? "
            "5. How much will Newey's Aston Martin improve in the second half?"
        ),
        "event_type": "technical",
        "published_at": make_dt(1),
    },
]


# ── Tier admission test questions (F1) ────────────────────────────────────────
TIER1_TESTS = [
    {
        "id": "t1_tech_1",
        "question": (
            "Explain the aerodynamic mechanism behind porpoising in 2022-regulation F1 cars. "
            "What causes the oscillation and how can teams mitigate it?"
        ),
        "expected_keywords": ["ground effect", "floor", "stall", "ride height", "venturi"],
        "max_score": 30,
    },
    {
        "id": "t1_strat_1",
        "question": (
            "A car is running P3, 8 laps into a 58-lap race on Medium tyres. The leader "
            "pits under a VSC triggered by a slow car. The P3 driver's team must decide: "
            "pit now or stay out? Walk through the decision matrix."
        ),
        "expected_keywords": ["track position", "delta", "undercut", "out-lap", "tyres"],
        "max_score": 30,
    },
    {
        "id": "t1_predict_1",
        "question": (
            "Based on current 2025 F1 season data (Ferrari strong in Spain/Monaco, "
            "McLaren strong in Australia, Red Bull winning in Bahrain), which constructor "
            "will win the 2025 Constructors Championship and why?"
        ),
        "expected_keywords": ["Ferrari", "McLaren", "Red Bull", "championship", "season"],
        "max_score": 25,
    },
    {
        "id": "t1_history_1",
        "question": (
            "Identify a historical F1 regulation reset that is analogous to the 2022 "
            "ground-effect return. What happened to the competitive order after that reset, "
            "and what does history suggest will happen in 2025–2026?"
        ),
        "expected_keywords": ["1983", "2009", "regulation", "reset", "order"],
        "max_score": 15,
    },
]

TIER2_TESTS = [
    {
        "id": "t2_valid_1",
        "question": (
            "A Tier-1 agent submits this theory: 'Ferrari's 2025 floor concept generates "
            "15% more downforce than any rival at Monza, which explains their recent wins.' "
            "Assess this theory for logical consistency, evidential support, and falsifiability."
        ),
        "expected_keywords": ["consistency", "evidence", "falsifiable", "Monza", "downforce"],
        "max_score": 50,
    },
    {
        "id": "t2_anom_1",
        "question": (
            "You notice the knowledge base contains both: (A) 'DRS adds 10–15 km/h on straights' "
            "and (B) 'DRS is ineffective at Baku as cars already reach terminal velocity.' "
            "Is this an anomaly? If so, how would you resolve it?"
        ),
        "expected_keywords": ["contradiction", "context", "terminal velocity", "circuit-specific"],
        "max_score": 50,
    },
]

TIER3_TESTS = [
    {
        "id": "t3_basic_1",
        "question": "What does DRS stand for and what does it do in F1?",
        "expected_keywords": ["Drag Reduction System", "wing", "straight"],
        "max_score": 33,
    },
    {
        "id": "t3_basic_2",
        "question": "Name the three Pirelli tyre compound colours used in a dry F1 race.",
        "expected_keywords": ["white", "yellow", "red", "hard", "medium", "soft"],
        "max_score": 34,
    },
    {
        "id": "t3_basic_3",
        "question": "How many constructors championships did Red Bull win from 2010 to 2023?",
        "expected_keywords": ["six", "6"],
        "max_score": 33,
    },
]

TIER_THRESHOLDS = {1: 85.0, 2: 70.0, 3: 50.0}
