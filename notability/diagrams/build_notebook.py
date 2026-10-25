"""Build the five-page notebook and editable vector SVGs, without importing the app.

Requires reportlab. Uses macOS Arial/Georgia or DejaVu fonts on Linux.
Run from anywhere: python notability/diagrams/build_notebook.py
All coordinates use a top-left origin. PDF text stays searchable; fonts are embedded.
"""
from __future__ import annotations

import html
import math
from pathlib import Path

from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import HexColor

OUT = Path(__file__).resolve().parents[1]
W, H = 900, 1200
REV = "e4521690f0b927f06fe8c50272efd6f926b461d0"
REPO = f"https://github.com/KrishnaPagrut/Trackback/blob/{REV}/"
PAPER = "#FAF8F2"
INK = "#192D38"
MUTED = "#54646C"
RULE = "#D9DFDC"
TEAL = "#166B60"
TEAL_LIGHT = "#E7F1EB"
RED = "#AF4938"
RED_LIGHT = "#F8EAE3"
BLUE = "#365C84"
BLUE_LIGHT = "#EAF0F6"
GOLD = "#85632D"
GOLD_LIGHT = "#F5EEDC"
WHITE = "#FFFFFF"


def fonts():
    mac = Path("/System/Library/Fonts/Supplemental")
    linux = Path("/usr/share/fonts/truetype/dejavu")
    specs = {
        "Body": (mac / "Arial.ttf", linux / "DejaVuSans.ttf"),
        "Bold": (mac / "Arial Bold.ttf", linux / "DejaVuSans-Bold.ttf"),
        "Serif": (mac / "Georgia.ttf", linux / "DejaVuSerif.ttf"),
        "Italic": (mac / "Georgia Italic.ttf", linux / "DejaVuSerif-Italic.ttf"),
    }
    for name, choices in specs.items():
        path = next((p for p in choices if p.exists()), None)
        if not path:
            raise RuntimeError(f"Install a TrueType font for {name}; see fonts()")
        pdfmetrics.registerFont(TTFont(name, str(path)))


class Notebook:
    def __init__(self):
        fonts()
        OUT.mkdir(exist_ok=True)
        self.c = canvas.Canvas(str(OUT / "project-ideation-notebook.pdf"), pagesize=(W, H), pageCompression=1)
        self.c.setTitle("Trackback — Project Ideation & Engineering Notebook")
        self.c.setAuthor("Trackback project team")
        self.c.setSubject("Retrospective repository-based notebook prepared for authentic review in Notability")
        self.c.setKeywords("Trackback, Cal Hacks 13.0, engineering notebook, Notability, retrospective")
        self.c.setViewerPreference("DisplayDocTitle", "true")
        self.svg = []
        self.page_no = 0
        self.text_bounds = []

    def rect(self, x, y, w, h, fill=WHITE, stroke=RULE, radius=12, sw=1):
        c = self.c
        c.setLineWidth(sw)
        c.setFillColor(HexColor(fill or PAPER))
        c.setStrokeColor(HexColor(stroke or PAPER))
        c.roundRect(x, H-y-h, w, h, radius, fill=bool(fill), stroke=bool(stroke))
        self.svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{fill or "none"}" stroke="{stroke or "none"}" stroke-width="{sw}"/>')

    def line(self, pts, color=RULE, width=1.5, dash=False, arrow=False):
        c = self.c
        c.setStrokeColor(HexColor(color)); c.setLineWidth(width)
        c.setDash([5, 4] if dash else [])
        path = c.beginPath(); path.moveTo(pts[0][0], H-pts[0][1])
        for x, y in pts[1:]:
            path.lineTo(x, H-y)
        c.drawPath(path)
        points = " ".join(f"{x},{y}" for x, y in pts)
        d = ' stroke-dasharray="5 4"' if dash else ""
        self.svg.append(f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="{width}" stroke-linejoin="round"{d}/>')
        c.setDash([])
        if arrow:
            x, y = pts[-1]; a, b = pts[-2]
            theta = math.atan2(y-b, x-a)
            size = 7
            corners = [(x,y), (x-size*math.cos(theta-.44), y-size*math.sin(theta-.44)), (x-size*math.cos(theta+.44), y-size*math.sin(theta+.44))]
            self.poly(corners, color, color)

    def poly(self, pts, fill=WHITE, stroke=RULE):
        c = self.c
        c.setFillColor(HexColor(fill)); c.setStrokeColor(HexColor(stroke)); c.setLineWidth(1.3)
        p = c.beginPath(); p.moveTo(pts[0][0], H-pts[0][1])
        for x, y in pts[1:]: p.lineTo(x,H-y)
        p.close(); c.drawPath(p, fill=1, stroke=1)
        points = " ".join(f"{x},{y}" for x,y in pts)
        self.svg.append(f'<polygon points="{points}" fill="{fill}" stroke="{stroke}" stroke-width="1.3"/>')

    def circle(self, x, y, r, fill, stroke=None):
        self.c.setFillColor(HexColor(fill)); self.c.setStrokeColor(HexColor(stroke or fill))
        self.c.circle(x,H-y,r,fill=1,stroke=bool(stroke))
        self.svg.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{fill}" stroke="{stroke or fill}"/>')

    def text(self, s, x, y, size=15, font="Body", color=INK, align="left"):
        # y denotes the top of the em box; ascent is fixed for consistent layouts.
        width = pdfmetrics.stringWidth(s,font,size)
        left = x-width/2 if align=="center" else x-width if align=="right" else x
        assert left >= 20 and left+width <= W-20, (self.page_no,s,left,width)
        assert y >= 16 and y+size <= H-16, (self.page_no,s,y)
        baseline = y+size*.83
        self.c.setFont(font,size); self.c.setFillColor(HexColor(color))
        self.c.drawString(left,H-baseline,s)
        fam = "Georgia, DejaVu Serif, serif" if font in ("Serif","Italic") else "Arial, DejaVu Sans, sans-serif"
        weight = "bold" if font=="Bold" else "normal"
        style = "italic" if font=="Italic" else "normal"
        self.svg.append(f'<text x="{left:.2f}" y="{baseline:.2f}" font-family="{fam}" font-size="{size}" font-weight="{weight}" font-style="{style}" fill="{color}">{html.escape(s)}</text>')
        self.text_bounds.append((self.page_no,left,y,width,size,s))
        return width

    def para(self, s, x, y, w, size=15, font="Body", color=MUTED, leading=None, max_h=None):
        leading = leading or size*1.35
        lines=[]
        for paragraph in s.split("\n"):
            line=""
            for word in paragraph.split():
                trial = f"{line} {word}".strip()
                if pdfmetrics.stringWidth(trial,font,size)>w and line:
                    lines.append(line); line=word
                else: line=trial
            lines.append(line)
        if max_h is not None:
            assert len(lines)*leading <= max_h+1, (self.page_no, s, len(lines)*leading,max_h)
        for i,s2 in enumerate(lines): self.text(s2,x,y+i*leading,size,font,color)
        return len(lines)*leading

    def badge(self, s, x, y, fill=TEAL_LIGHT, color=TEAL, size=11.5):
        w=pdfmetrics.stringWidth(s,"Bold",size)+22
        self.rect(x,y,w,25,fill,None,6)
        self.text(s,x+11,y+7,size,"Bold",color)
        return w

    def card(self, x,y,w,h,title,body="",fill=WHITE,accent=TEAL,title_size=19,body_size=14.5):
        self.rect(x,y,w,h,fill,RULE,12)
        pad=10 if h<100 else 16
        gap=4 if h<100 else 9
        self.rect(x+pad,y+pad,3,20,accent,None,1)
        th=self.para(title,x+pad+12,y+pad,w-2*pad-12,title_size,"Bold",INK,leading=title_size*1.1)
        if body:
            self.para(body,x+pad,y+pad+th+gap,w-2*pad,body_size,color=MUTED,leading=body_size*1.25,max_h=h-pad-th-gap-6)

    def centered(self,s,x,y,w,h,size=15,font="Bold",color=INK):
        lines=s.split("\n"); leading=size*1.18
        top=y+(h-len(lines)*leading)/2
        for i,l in enumerate(lines): self.text(l,x+w/2,top+i*leading,size,font,color,"center")

    def decision(self,x,y,w,h,label):
        self.poly([(x+w/2,y),(x+w,y+h/2),(x+w/2,y+h),(x,y+h/2)],GOLD_LIGHT,GOLD)
        self.centered(label,x,y,w,h,14)

    def start(self, no, section, title, subtitle):
        self.page_no=no
        self.svg=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',f'<title>{html.escape(section)} — Trackback</title>']
        self.rect(0,0,W,H,PAPER,None,0)
        self.c.bookmarkPage(f"p{no}")
        self.c.addOutlineEntry(f"{no:02d}  {section}",f"p{no}",0,False)
        self.text("TRACKBACK",52,40,13,"Bold",INK)
        self.text("PROJECT IDEATION & ENGINEERING NOTEBOOK",160,42,10.5,"Body",MUTED)
        for n in range(1,6):
            x=713+(n-1)*29
            if n==no: self.circle(x,48,12,INK)
            self.text(str(n),x,42,11,"Bold",WHITE if n==no else MUTED,"center")
            self.c.linkRect("",f"p{n}",(x-13,H-62,x+13,H-34),relative=0,thickness=0)
        self.line([(52,75),(848,75)],RULE,1)
        self.text(f"{no:02d}  /  {section.upper()}",52,96,11.5,"Bold",TEAL)
        self.text(title,52,122,36,"Serif")
        self.para(subtitle,52,174,790,15.5,color=MUTED,leading=21,max_h=48)

    def notes(self, prompt, y=1035, h=90):
        self.rect(52,y,796,h,None,RULE,8)
        self.text("YOUR REVIEW",68,y+13,10.5,"Bold",TEAL)
        self.text(prompt,168,y+12,12,"Body",MUTED)
        for yy in range(int(y+43),int(y+h-8),18):
            for xx in range(69,836,18): self.circle(xx,yy,.65,"#D1D9D4")

    def footer(self, sources):
        self.line([(52,1142),(848,1142)],RULE,1)
        x=52
        self.text("EVIDENCE",x,1152,9.5,"Bold",MUTED); x+=61
        for label,path in sources:
            width=self.text(label,x,1152,9.5,"Body",MUTED)
            self.c.linkURL(REPO+path,(x,H-1164,x+width,H-1150),relative=0,thickness=0)
            x+=width+17
        self.text("RETROSPECTIVE  ·  SOURCE e452169  ·  CAL HACKS 13.0",52,1172,9.5,"Body",MUTED)
        self.text(f"{self.page_no:02d} / 05",848,1172,10,"Bold",INK,"right")
        self.svg.append("</svg>")
        (OUT/"diagrams"/f"{self.page_no:02d}-{['vision','ideation','journey','architecture','development'][self.page_no-1]}.svg").write_text("\n".join(self.svg))
        self.c.showPage()


def vision(n):
    n.start(1,"The problem & our vision","One correction. Many consequences.",
            "Finance agents build on each other’s work. When an input changes later,\nthe team needs to know what broke, what still holds, and who must act.")
    n.badge("FICTIONAL CASE STUDY · TIDEWALL’S SIX GYMS",52,240)
    n.text("A billing duplicate reaches beyond the ledger.",52,285,24,"Serif")
    n.para("A $118,000 March revenue correction can change a lender certificate, a board deck, bonuses and a tax estimate. Finding every dependency by hand is the work Trackback targets.",52,323,765,17,leading=24,max_h=78)

    n.text("THE SOURCE",52,425,11,"Bold",RED)
    n.text("THE CORRECTION ENGINE",333,425,11,"Bold",TEAL)
    n.text("THE RESPONSE",641,425,11,"Bold",INK)
    # Diagram edges first, so nodes always sit cleanly above the connectors.
    n.line([(270,573),(321,573)],RED,2,arrow=True)
    n.line([(581,573),(608,573),(608,505),(635,505)],TEAL,2,arrow=True)
    n.line([(581,573),(608,573),(608,631),(635,631)],BLUE,2,arrow=True)
    n.line([(608,631),(608,757),(635,757)],GOLD,2,arrow=True)
    n.card(52,500,218,146,"Correct the source","Billing export v1 → v2\nRecord the changed facts and when they became known.",RED_LIGHT,RED,18,15)
    # A dark hero card anchors the diagram.
    n.rect(321,476,260,194,INK,None,12)
    n.text("TRACKBACK",343,496,11.5,"Bold","#B6D9CE")
    n.para("Trace the impact",343,526,218,25,"Serif",WHITE,leading=29)
    n.para("Follow read receipts.\nRecompute in code.\nPing affected agents.",343,574,218,16,color="#DCEAE5",leading=25)
    n.card(635,459,213,92,"Still valid","Keep it, with a reason.",TEAL_LIGHT,TEAL,18,14.5)
    n.card(635,585,213,92,"Reworked","Version the revised work.",BLUE_LIGHT,BLUE,18,14.5)
    n.card(635,711,213,92,"Needs a person","Propose a controlled fix.",GOLD_LIGHT,GOLD,18,14.5)
    n.para("Central insight\nRecord what each output actually consumed, then trace corrections forward.",52,704,518,18,"Serif",INK,leading=26,max_h=85)

    n.rect(52,841,796,91,TEAL_LIGHT,None,12)
    n.text("THE DEMO’S TURNING POINT",72,858,11,"Bold",TEAL)
    n.text("2.95×",72,883,29,"Serif",INK)
    n.line([(176,900),(207,900)],INK,1.8,arrow=True)
    n.text("3.03×",224,883,29,"Serif",INK)
    n.para("The leverage calculation crosses a 3.00× covenant limit.\nA small-looking revenue error becomes a consequential decision.",340,866,485,15.5,color=INK,leading=23,max_h=60)
    n.text("BUILT FOR",52,962,11,"Bold",TEAL)
    n.para("Close accountants & reporting analysts: targeted rework.\nControllers & CFOs: evidence, approval and an auditable correction trail.",157,956,680,15.5,color=INK,leading=24,max_h=56)
    n.notes("Circle the downstream consequence that matters most to a finance team.")
    n.footer([("README · product", "README.md"),("Live E11 flow", "backend/trackback/live.py"),("Recorded decisions", "DECISIONS.md")])


def ideation(n):
    n.start(2,"Ideation & exploration","Why selective repair?",
            "Retrospective map: reconstructed from the implementation and decision log.\nThis records the reasoning visible in the repository, not an earlier brainstorming session.")
    # Six branches orbit a single central insight.
    for pts,color in [([(330,502),(306,502),(306,334),(292,334)],RED),
                      ([(570,502),(594,502),(594,334),(608,334)],TEAL),
                      ([(330,524),(292,524)],GOLD), ([(570,524),(608,524)],TEAL),
                      ([(330,548),(306,548),(306,739),(292,739)],BLUE),
                      ([(570,548),(594,548),(594,739),(608,739)],BLUE)]:
        n.line(pts,color,2)
    n.card(52,258,240,155,"01  Problem","Late corrections\nCross-agent dependencies\nActions already executed",RED_LIGHT,RED,18,16)
    n.card(608,258,240,155,"02  Trust","Exact versions consumed\nNo future-data leakage\nHuman approval for fixes",TEAL_LIGHT,TEAL,18,16)
    n.card(52,455,240,170,"03  Alternatives","Rerun every agent: expensive.\nFlag every descendant: noisy.\nBoth exist as evaluation baselines.",GOLD_LIGHT,GOLD,18,15.5)
    n.card(608,455,240,170,"04  Implemented","Recompute first.\nCheck relevance and materiality.\nBundle suspect work into one ping per agent per wave.",TEAL_LIGHT,TEAL,18,15)
    n.card(52,667,240,155,"05  Evidence","Two clocks: effective time and known time.\nPinned reads preserve what an agent could know.",BLUE_LIGHT,BLUE,18,15)
    n.card(608,667,240,155,"06  Control","Receipts verify dependencies.\nCaps bound rework.\nCompensations repair actions that already happened.",BLUE_LIGHT,BLUE,18,15)
    n.rect(330,465,240,123,INK,None,16)
    n.text("THE DESIGN QUESTION",450,486,10.5,"Bold","#B6D9CE","center")
    n.centered("What actually\nneeds to change?",330,510,240,64,23,"Serif",WHITE)

    n.text("THREE CHOICES THAT SHAPE THE BUILD",52,863,11,"Bold",TEAL)
    choices=[
        ("Precision over blanket reruns", "Identical values stop the walk; below-threshold changes still flow to children, preserving aggregate effects."),
        ("Reproducibility over live dependence", "Record, replay and scripted modes keep the demo usable offline; the snapshot contains mixed response origins."),
        ("Verified scope over a rewrite", "The Oct 24 decision kept the six-gym world and added Jade + lessons instead of replacing it with the 48-gym proposal."),
    ]
    for i,(title,body) in enumerate(choices):
        y=893+i*43
        n.text(f"0{i+1}",52,y,12,"Bold",TEAL)
        n.text(title,82,y,13.5,"Bold")
        n.para(body,365,y,483,12.5,leading=16,max_h=34)
    n.notes("Highlight one tradeoff to revisit. Add the alternative and the evidence needed.")
    n.footer([("DECISIONS · tradeoffs", "DECISIONS.md"),("Propagation semantics", "backend/trackback/core/propagate.py"),("Evaluation baselines", "backend/scripts/eval.py")])


def journey(n):
    n.start(3,"Complete user journey","Follow the correction.",
            "One main path, with explicit stops for uncertain input, agent review and human control.\nThe Stage walkthrough and Deep workspace expose the same backend.")
    # Legend uses words as well as colors.
    n.badge("USER",52,229,BLUE_LIGHT,BLUE,10.5)
    n.badge("SYSTEM",137,229,TEAL_LIGHT,TEAL,10.5)
    n.badge("DECISION / GUARD",240,229,GOLD_LIGHT,GOLD,10.5)
    n.text("Solid arrows = flow   ·   Dashed = optional model path",848,236,11,"Body",MUTED,"right")

    # Main spine and branches. Edges are intentionally routed outside all cards.
    n.line([(450,338),(450,365)],TEAL,1.8,arrow=True)
    n.line([(450,443),(450,473)],TEAL,1.8,arrow=True)
    n.line([(340,404),(250,404)],RED,1.8,arrow=True)
    n.line([(140,369),(140,307),(260,307)],RED,1.5,arrow=True)
    n.line([(450,555),(450,582)],TEAL,1.8,arrow=True)
    n.line([(335,624),(228,624)],TEAL,1.8,arrow=True)
    n.line([(140,666),(140,718),(260,718)],TEAL,1.8,arrow=True)
    n.line([(565,624),(675,624)],BLUE,1.8,arrow=True)
    n.line([(761,680),(761,702)],BLUE,1.8,arrow=True)
    n.line([(675,741),(640,741)],BLUE,1.8,arrow=True)
    n.line([(450,768),(450,808)],TEAL,1.8,arrow=True)
    n.line([(260,751),(228,751),(228,800),(218,800)],GOLD,1.6,arrow=True)
    n.line([(761,780),(761,829)],GOLD,1.8,arrow=True)
    n.line([(718,915),(718,949)],TEAL,1.5,arrow=True)
    n.line([(805,915),(805,949)],RED,1.5,arrow=True)
    n.line([(761,550),(761,586)],BLUE,1.4,dash=True,arrow=True)

    n.card(260,272,380,66,"01  Choose a correction","Space: E11 story · Deep edits · Kiosk presets/paste",BLUE_LIGHT,BLUE,18,12.5)
    n.decision(340,365,220,78,"Custom input\nresolves clearly?")
    n.text("NO",280,386,10.5,"Bold",RED)
    n.text("YES / PRESET",463,451,10.5,"Bold",TEAL)
    n.card(52,369,198,83,"Clarify & retry","Unmatched text → revise it. Invalid values/source → 400.",RED_LIGHT,RED,16,12.5)
    n.card(260,473,380,82,"02  Version → diff → recompute","Store the correction; follow recorded dependencies. Evaluate formulas, relevance and materiality.",TEAL_LIGHT,TEAL,18,13.5)
    n.decision(335,582,230,84,"Agent re-check\nneeded?")
    n.text("NO",273,608,10.5,"Bold",TEAL)
    n.text("YES",604,608,10.5,"Bold",BLUE)
    n.card(52,586,176,80,"Keep the reason","Clear unchanged work; preserve recalculations.",TEAL_LIGHT,TEAL,15.5,12.5)
    n.card(675,586,173,94,"03  Ping owner","One bundle per agent.\nReceipt / cap failure\n→ human review.",BLUE_LIGHT,BLUE,15.5,12)
    n.card(675,453,173,97,"Model path","Replay: cached response.\nRecord: Anthropic API.\nScripted: local stand-in.",WHITE,BLUE,15.5,12)
    n.card(675,702,173,78,"Agent replies","Still valid · reworked\n· needs human",BLUE_LIGHT,BLUE,16,12.5)
    n.card(260,695,380,73,"04  Review the impact","Inspect changed work, cleared work, ping replies and proposed compensations.",TEAL_LIGHT,TEAL,18,13)
    n.card(52,765,166,231,"Jade + lessons","For supported finance cases, check four judgment calls.\n\nOverrules / rejections propose lessons.\n\nRegression gate → Controller approval → future playbook.",GOLD_LIGHT,GOLD,17,13)
    n.card(260,808,380,121,"05  Inspect & verify","D: lineage, approvals, Jade, lessons and Scorecard.\nT: inspect evidence as of the decision time.\nFuture evidence is refused (403 / 404).\nR: reset the demo.",WHITE,TEAL,18,13.5)
    n.text("NEEDS HUMAN",748,805,9.4,"Bold",GOLD,"right")
    n.card(675,829,173,86,"Approve + guard","Compensation proposal; separate approver; fresh evidence; open period.",GOLD_LIGHT,GOLD,15.5,12)
    n.text("PASS",699,929,10,"Bold",TEAL,"center")
    n.text("NO",822,929,10,"Bold",RED,"center")
    n.rect(675,949,83,47,TEAL_LIGHT,None,8)
    n.centered("Record\nlocal effect",675,949,83,47,12,"Bold",TEAL)
    n.rect(768,949,80,47,RED_LIGHT,None,8)
    n.centered("Rejected /\nblocked",768,949,80,47,11.5,"Bold",RED)
    n.para("Demo scope: E11 scripts rejection + re-draft; Stage’s lesson beat submits Controller approval. Deep allows explicit review. Effects stay in the local demo; no bank connection.",260,949,380,12,leading=16,max_h=65)
    n.notes("Trace one successful correction. Circle where you would stop for more evidence.",1040,85)
    n.footer([("UI flow", "frontend/src/stage/Stage.tsx"),("API + validation", "backend/trackback/api.py"),("Waves", "backend/trackback/core/waves.py"),("Execution guards", "backend/trackback/corrections.py")])


def architecture(n):
    n.start(4,"Technical architecture","A graph with memory and guardrails.",
            "One Python service hosts the demo API, time-pinned documents and built frontend.\nReplay uses cached or local responses; external model calls require record mode.")
    n.card(52,234,796,73,"Browser · React 19 / TypeScript / Vite 8","Tailwind CSS 4 · React Flow + Dagre · Stage / Deep / Scorecard / Lyft reconstruction",BLUE_LIGHT,BLUE,21,15)
    n.line([(245,307),(245,348)],BLUE,1.8,arrow=True)
    n.text("HTTP JSON",262,320,10.5,"Bold",BLUE)
    n.card(52,348,386,85,"FastAPI + Uvicorn","API: corrections, graph, approvals, lessons, snapshots. Protocol routes: pings, challenges and SSE events.",WHITE,TEAL,20,13.5)
    n.card(462,348,386,85,"Time-pinned evidence service","Memento routes /r · /tg · /m · /tm. Reads bind to the run’s pin; later evidence returns 403 / 404.",WHITE,TEAL,20,13.5)
    n.line([(245,433),(245,454),(312,454),(312,510)],TEAL,1.8,arrow=True)
    n.line([(730,486),(730,433)],BLUE,1.8,arrow=True)
    n.text("PINNED TOOL READS",742,452,9.3,"Bold",BLUE)

    n.rect(52,470,520,312,None,RULE,14)
    n.text("CORRECTION + CONTROL MODULES",71,483,10.5,"Bold",TEAL)
    n.card(72,510,480,73,"Core: diff → propagate → waves → pings","Formula evaluation · version graph · verified receipts · bounded rework",TEAL_LIGHT,TEAL,18,13)
    n.line([(552,547),(610,547)],BLUE,1.8,arrow=True)
    n.text("PING",582,530,9,"Bold",BLUE,"center")
    n.line([(610,568),(552,568)],BLUE,1.4,arrow=True)
    n.text("REPLY",584,575,9,"Bold",BLUE,"center")
    n.line([(183,583),(183,609)],TEAL,1.4,arrow=True)
    n.line([(431,583),(431,609)],TEAL,1.4,arrow=True)
    n.card(72,609,230,94,"Finance domain pack","Materiality, periods, ledger, tie-outs, compensation catalog.",WHITE,TEAL,16.5,13)
    n.card(322,609,230,94,"Jade + lessons","Rule-based judgment review; recall, regression gate, prospective checks.",GOLD_LIGHT,GOLD,16.5,13)
    n.rect(72,720,480,44,WHITE,RULE,8)
    n.centered("Approvals → freshness / figure fence → simulated effect",72,720,480,44,14,"Bold")
    n.line([(183,703),(183,720)],TEAL,1.3,arrow=True)
    n.line([(431,703),(431,720)],GOLD,1.3,arrow=True)

    n.card(610,486,238,104,"Agent runtime","Close Accountant\nReporting Analyst\nCovenant & Compensation",BLUE_LIGHT,BLUE,19,13.5)
    n.line([(729,590),(729,621)],BLUE,1.6,arrow=True)
    n.card(610,621,238,81,"LLM gateway","record / replay / scripted\nCache keys include the pinned corpus.",WHITE,BLUE,18,12.5)
    n.line([(729,702),(729,731)],BLUE,1.4,dash=True,arrow=True)
    n.text("RECORD ONLY",752,710,9.5,"Bold",BLUE)
    n.rect(610,731,238,51,BLUE_LIGHT,None,8)
    n.centered("External: Anthropic API\nAgent / prose / judge calls",610,731,238,51,13,"Body",BLUE)

    n.line([(312,782),(312,841)],TEAL,1.8,arrow=True)
    n.text("READ / WRITE",328,808,10,"Bold",TEAL)
    n.line([(848,659),(865,659),(865,815),(730,815),(730,841)],BLUE,1.5,arrow=True)
    n.text("CACHE",791,822,9.5,"Bold",BLUE)
    n.line([(848,390),(879,390),(879,826),(835,826),(835,841)],TEAL,1.2,arrow=True)
    n.rect(52,841,796,98,INK,None,12)
    n.text("SHARED SQLITE · VERSIONED EVIDENCE + EVENT HISTORY",74,859,12,"Bold","#B6D9CE")
    n.para("Sources / claim versions · artifacts / justifications · consumption receipts\nRuns / reads · waves / pings / outbox · approvals / ledger / effects · lessons · LLM cache",74,888,752,14.5,color=WHITE,leading=22,max_h=50)
    n.para("Offline builders restore the canonical snapshot; evaluation scripts compare against YAML answer keys.\nAlso implemented: stdio MCP read tools, Docker/Fly configuration and a Vercel entry with a /tmp database.\nMCP/A2A notification adapters and a second domain pack remain future work.",52,961,796,13.5,leading=20,max_h=65)
    n.notes("Mark the first boundary to change for multiple concurrent customer sessions.",1040,85)
    n.footer([("Service entry", "backend/trackback/main.py"),("Core / pack boundary", "backend/trackback/core/domain.py"),("MCP read tools", "backend/trackback/mcp_server.py"),("Vercel entry", "api/index.py")])


def development(n):
    n.start(5,"Development journey & lessons","From a working graph to a usable demo.",
            "Actual Git milestones, shown in Pacific time. Engineering lessons below come from\nthe decision log and source tests; they are not a reconstructed hour-by-hour diary.")
    n.text("THE BUILD RECORD",52,238,11,"Bold",TEAL)
    n.text("STORED EVALUATION EVIDENCE",610,238,11,"Bold",TEAL)
    n.line([(66,284),(66,714)],TEAL,2)
    events=[
        ("23 OCT · 22:57", "06bbbc9", "Offline demo + runtime fixes", "Snapshot restore via SQLite backup; proxies and verification tools arrive in the working demo."),
        ("24 OCT · 11:27", "4b6031c", "Jade, lessons and explanations", "Add judgment review, lesson gating and recall; expose the learning sequence and hover explanations."),
        ("24 OCT · 11:46", "fcc8cb3", "Make the interface teach itself", "Opt-in kiosk, plain-language counters and a first-visit guide explain the Deep workspace."),
        ("24 OCT · 12:11", "48964da", "Keep the kiosk loop running", "Synthetic mouse movement no longer interrupts the attract loop; later screenshots document the check."),
        ("24 OCT · 15:34", "e452169", "Simplify the story; package hosting", "Scorecard naming, clearer dependency lines and a Vercel entry with committed frontend assets."),
    ]
    for i,(date,sha,title,body) in enumerate(events):
        y=270+i*105
        n.circle(66,y+13,7,TEAL)
        n.text(date,89,y,11,"Bold",TEAL)
        n.text(sha,550,y,11,"Body",MUTED,"right")
        n.text(title,89,y+22,18,"Bold")
        n.para(body,89,y+49,463,13.5,leading=18,max_h=42)
        n.c.linkURL(f"https://github.com/KrishnaPagrut/Trackback/commit/{sha}",(89,H-y-18,550,H-y),relative=0,thickness=0)
    stats=[("0 / 288", "future-data leaks", "Adversarial pinned fetches."),
           ("162 / 162", "identical replay artifacts", "Byte-for-byte reconstruction."),
           ("13 / 13", "planted mistakes caught", "Jade: 0 false overrules\non 63 correct claims.")]
    for i,(value,title,body) in enumerate(stats):
        y=270+i*131
        n.rect(610,y,238,115,TEAL_LIGHT,None,12)
        n.text(value,630,y+16,30,"Serif",TEAL)
        n.text(title,630,y+55,14,"Bold")
        n.para(body,630,y+78,199,12.5,leading=16,max_h=34)
    n.para("Reported by committed replay evaluations, not rerun for this notebook. These measure the seeded demo cases, not production reliability.",610,673,238,12.5,leading=18,max_h=76)

    n.text("WHAT THE ENGINEERING TAUGHT US",52,784,11,"Bold",TEAL)
    n.card(52,811,252,116,"Reset without stale reads","Replacing a live DB left stale handles. SQLite backup preserves readers; concurrent-reset tests cover it.",WHITE,TEAL,16,13)
    n.card(324,811,252,116,"Match build and replay","Scripted and replay prose diverged. Both now reuse the same recorded response when the cache key matches.",WHITE,BLUE,16,13)
    n.card(596,811,252,116,"Explain the graph","Stage shows one beat at a time; Deep exposes the evidence. Layout sizes and a type-floor check improved legibility.",WHITE,GOLD,16,13)
    n.text("NOW",52,947,11,"Bold",TEAL)
    n.para("Correction tracing, agent replies, approvals, time travel, Jade and gated lessons work in the offline demo.",110,943,730,13.5,leading=19,max_h=40)
    n.text("NEXT",52,988,11,"Bold",GOLD)
    n.para("Record the remaining scripted rework; wire prose critique; isolate sessions; add notification adapters. Current limits: mixed cache origins, code-based Jade, one shared world per instance.",110,984,730,13.5,leading=19,max_h=42)
    n.notes("Team reflection: next experiment / owner / evidence of success / review date.",1040,85)
    n.footer([("STATUS · scope", "STATUS.md"),("Engineering decisions", "DECISIONS.md"),("Evaluation JSON", "data/eval/latest.json"),("Reset regression tests", "backend/tests/test_snapshot_restore.py")])


def main():
    n=Notebook()
    for f in [vision,ideation,journey,architecture,development]: f(n)
    n.c.save()
    print(f"Generated five pages: {OUT / 'project-ideation-notebook.pdf'}")
    print("Editable SVG pages and this generator are in notability/diagrams/.")


if __name__ == "__main__":
    main()
