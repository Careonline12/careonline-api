"""
care.on.line — Moteur de recommandation + Générateur de guide PDF
Usage: python engine.py <quiz_data.json>  →  guide_beaute_<prenom>.pdf
"""
import json, sys, os, textwrap
import pandas as pd
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak, KeepTogether
)
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# ══════════════════════════════════════════════════════════════
#  BRAND COLORS
# ══════════════════════════════════════════════════════════════
C_DEEP  = colors.HexColor("#2e1f1a")
C_ROSE  = colors.HexColor("#d4877a")
C_GOLD  = colors.HexColor("#c8a96e")
C_BLUSH = colors.HexColor("#f2ddd8")
C_CREAM = colors.HexColor("#faf6f1")
C_MUTED = colors.HexColor("#8a7068")
C_CREAM2= colors.HexColor("#f2ece4")
C_WHITE = colors.white
C_BORDER= colors.HexColor("#e6d8d2")

W, H = A4  # 210 × 297 mm

# ══════════════════════════════════════════════════════════════
#  STYLES
# ══════════════════════════════════════════════════════════════
def make_styles():
    base = dict(fontName="Helvetica", fontSize=10, leading=14,
                textColor=C_DEEP, spaceAfter=4)
    return {
        "cover_brand": ParagraphStyle("cover_brand", fontName="Helvetica",
            fontSize=11, textColor=C_MUTED, letterSpacing=3,
            alignment=TA_CENTER, spaceAfter=8),
        "cover_title": ParagraphStyle("cover_title", fontName="Helvetica-Bold",
            fontSize=32, textColor=C_DEEP, alignment=TA_CENTER,
            leading=38, spaceAfter=6),
        "cover_sub":   ParagraphStyle("cover_sub", fontName="Helvetica",
            fontSize=13, textColor=C_ROSE, alignment=TA_CENTER,
            leading=18, spaceAfter=24),
        "cover_name":  ParagraphStyle("cover_name", fontName="Helvetica",
            fontSize=15, textColor=C_GOLD, alignment=TA_CENTER,
            spaceAfter=6),
        "section_eyebrow": ParagraphStyle("section_eyebrow", fontName="Helvetica",
            fontSize=8, textColor=C_GOLD, letterSpacing=2,
            spaceAfter=4),
        "section_title": ParagraphStyle("section_title", fontName="Helvetica-Bold",
            fontSize=20, textColor=C_DEEP, leading=24, spaceAfter=6),
        "section_desc": ParagraphStyle("section_desc", fontName="Helvetica",
            fontSize=9, textColor=C_MUTED, leading=14, spaceAfter=14),
        "h2": ParagraphStyle("h2", fontName="Helvetica-Bold",
            fontSize=14, textColor=C_DEEP, spaceAfter=6, spaceBefore=12),
        "h3": ParagraphStyle("h3", fontName="Helvetica-Bold",
            fontSize=11, textColor=C_ROSE, spaceAfter=4, spaceBefore=8),
        "body": ParagraphStyle("body", **base),
        "body_muted": ParagraphStyle("body_muted", fontName="Helvetica",
            fontSize=9, textColor=C_MUTED, leading=13, spaceAfter=4),
        "label": ParagraphStyle("label", fontName="Helvetica",
            fontSize=8, textColor=C_MUTED, letterSpacing=1, spaceAfter=2),
        "value": ParagraphStyle("value", fontName="Helvetica-Bold",
            fontSize=9, textColor=C_DEEP, leading=13, spaceAfter=4),
        "tag": ParagraphStyle("tag", fontName="Helvetica",
            fontSize=8, textColor=C_ROSE, spaceAfter=2),
        "product_name": ParagraphStyle("product_name", fontName="Helvetica-Bold",
            fontSize=12, textColor=C_DEEP, leading=15, spaceAfter=2),
        "product_brand": ParagraphStyle("product_brand", fontName="Helvetica",
            fontSize=10, textColor=C_GOLD, spaceAfter=4),
        "product_body": ParagraphStyle("product_body", fontName="Helvetica",
            fontSize=8.5, textColor=C_MUTED, leading=13, spaceAfter=6),
        "step_label": ParagraphStyle("step_label", fontName="Helvetica-Bold",
            fontSize=8, textColor=C_WHITE, alignment=TA_CENTER),
        "routine_title": ParagraphStyle("routine_title", fontName="Helvetica-Bold",
            fontSize=13, textColor=C_DEEP, spaceAfter=8, spaceBefore=14),
        "price": ParagraphStyle("price", fontName="Helvetica-Bold",
            fontSize=11, textColor=C_ROSE, spaceAfter=4),
    }

STYLES = make_styles()

# ══════════════════════════════════════════════════════════════
#  MATCHING ENGINE
# ══════════════════════════════════════════════════════════════
BUDGET_ORDER = {
    "< 10 euros": 0,
    "Entre 10 et 29 €": 1,
    "Entre 30 et 69 €": 2,
    "Entre 70 et 100 €": 3,
    "> 100 €": 4,
}

# Map quiz budget values → DB format
BUDGET_MAP = {
    "< 10 euros":      "< 10 euros",
    "Entre 10 et 29 €": "Entre 10 et 29 €",
    "Entre 30 et 69 €": "Entre 30 et 69 €",
    "Entre 70 et 100 €": "Entre 70 et 100 €",
    "> 100 €":         "> 100 €",
}

def derive_type_peau(quiz):
    """Determine type de peau from quiz answers."""
    apres_creme = quiz.get("apres_creme", "")
    apres_douche = quiz.get("apres_douche", "")
    
    scores = {"seche": 0, "normale": 0, "mixte": 0, "grasse": 0}
    
    creme_map = {
        "Peau très sèche": {"seche": 2},
        "Peau sèche":      {"seche": 2},
        "Peau normale":    {"normale": 2},
        "Peau mixte":      {"mixte": 2},
        "Peau grasse":     {"grasse": 2},
    }
    douche_map = {
        "Peau sèche":      {"seche": 1},
        "A tendance sèche":{"seche": 1},
        "Peau mixte":      {"mixte": 1},
        "Peau grasse":     {"grasse": 1},
    }
    
    for k, v in creme_map.get(apres_creme, {}).items():
        scores[k] += v
    for k, v in douche_map.get(apres_douche, {}).items():
        scores[k] += v
    
    best = max(scores, key=lambda k: scores[k])
    map_to_label = {
        "seche": "Peau sèche",
        "normale": "Peau normale",
        "mixte": "Peau mixte",
        "grasse": "Peau grasse"
    }
    return map_to_label.get(best, "Peau normale")


def derive_etats_peau(quiz):
    """Return list of états de peau (can be multiple)."""
    etats = []
    
    reactions = quiz.get("reactions_peau", "")
    sport_rx   = quiz.get("reaction_sport", "")
    acne       = quiz.get("acne", "")
    stress     = quiz.get("stress", "")
    rides      = quiz.get("rides", "")
    tabac      = quiz.get("tabac", "")
    pollution  = quiz.get("pollution_air", "")
    expo       = quiz.get("exposition_autre", [])
    hyperp     = quiz.get("hyperpigmentation", "")
    preoccup   = quiz.get("premiere_preoccupation", "")
    
    # Sensible
    if reactions in ["Peau très réactive", "Peau réactive"] or \
       sport_rx  in ["Peau très réactive", "Peau réactive"]:
        etats.append("Peau sensible")
    
    # Réactive
    if reactions in ["Peau très réactive", "Peau réactive"] or \
       sport_rx  in ["Peau très réactive", "Peau réactive"]:
        etats.append("Peau réactive")
    
    # Acnéïque
    if acne in ["Peau acnéique", "Peau à tendance acnéïque"]:
        etats.append("Peau acnéïque")
    
    # Mature
    if rides in ["Ridules naissantes", "Rides naissantes", "Rides installées"]:
        etats.append("Peau mature")
    
    # Stressée
    if stress in ["Oui", "Par période"]:
        etats.append("Peau stressée")
    
    # Déshydratée
    deshyd_signals = 0
    if tabac in ["Oui régulièrement", "Oui occasionnellement"]:
        deshyd_signals += 1
    if pollution in ["Haute", "Modérée"]:
        deshyd_signals += 1
    if any(e in expo for e in ["Eau calcaire", "Climatisation", "Chauffage électrique"]):
        deshyd_signals += 1
    if rides != "Pas de rides":
        deshyd_signals += 1
    if deshyd_signals >= 2:
        etats.append("Peau déshydratée")
    
    # Contour œil cerné
    if preoccup in ["Mes cernes", "Mes poches"]:
        etats.append("Contour œil cerné")
    
    return list(dict.fromkeys(etats)) or ["Peau sensible"]  # default


def derive_phototype(quiz):
    """Determine phototype from bain soleil answer."""
    bain = quiz.get("apres_bain_soleil", "Phototype 3")
    if "Phototype" in str(bain):
        return bain
    return "Phototype 3"


def preoccupation_match(user_preoccup, cell_value):
    """Check if user preoccupation matches a cell containing multiple values."""
    if pd.isna(cell_value):
        return False
    cell_str = str(cell_value)
    
    # Direct mappings from quiz values to DB values
    mapping = {
        "Mon acné":                  ["Acné", "Points noirs et blancs", "Peau qui brille"],
        "Mes points noirs/boutons blancs": ["Points noirs et blancs", "Acné"],
        "Ma peau sèche":             ["Peau sèche", "Peau sèche\nRides et ridules naissantes"],
        "Mes rides et ridules naissantes": ["Peau sèche\nRides et ridules naissantes", "Rides et ridules naissantes"],
        "Mes rides bien installées": ["Rides installées"],
        "Mon teint terne":           ["Teint terne"],
        "Mes cernes":                ["Cernes\nPoches", "Cernes"],
        "Mes poches":                ["Cernes\nPoches", "Poches"],
        "Mes rougeurs":              ["Rougeurs"],
        "Ma peau qui brille":        ["Acné\nPeau qui brille\nPoints noirs et blancs", "Peau qui brille"],
    }
    
    targets = mapping.get(user_preoccup, [user_preoccup])
    for target in targets:
        if target in cell_str or any(t in cell_str for t in target.split("\n")):
            return True
    return False


def cell_contains(cell_value, user_value):
    """Check if a multi-value cell contains the user's value."""
    if pd.isna(cell_value):
        return False
    cell_str = str(cell_value)
    return user_value in cell_str


def budget_affordable(product_budget, user_budget):
    """Return True if product's budget <= user's max budget."""
    if pd.isna(product_budget):
        return True
    pb = BUDGET_ORDER.get(str(product_budget).strip(), 99)
    ub = BUDGET_ORDER.get(str(user_budget).strip(), 99)
    return pb <= ub


def match_products(quiz, df_routine, df_products):
    """
    Main matching function.
    Returns dict: {routine: {etape: [product_info, ...]}}
    """
    type_peau  = derive_type_peau(quiz)
    etats_peau = derive_etats_peau(quiz)
    phototype  = derive_phototype(quiz)
    nb_produits = quiz.get("nombre_produits", "3 produits")
    budget_net  = quiz.get("budget_nettoyant", "Entre 10 et 29 €")
    budget_sq   = quiz.get("budget_soin_quotidien", "Entre 30 et 69 €")
    circuit     = quiz.get("circuit_achats", [])
    allergies   = quiz.get("allergies", [])
    mentions    = quiz.get("mentions", [])
    preoccup    = quiz.get("premiere_preoccupation", "Ma peau sèche")
    
    # Build product lookup dict by name
    product_lookup = {}
    for _, row in df_products.iterrows():
        name = str(row.get("{{Nom_produit}} ", "")).strip()
        if name and name != "nan":
            product_lookup[name] = row
    
    results = {"Morning": {}, "Evening": {}}
    
    for _, row in df_routine.iterrows():
        # --- FILTERS ---
        # 1. Préoccupation
        if not preoccupation_match(preoccup, row.get("{{1ere_préoccupation}}")):
            continue
        
        # 2. Type de peau (col index 2)
        type_col = df_routine.columns[2]
        if not cell_contains(row.get(type_col), type_peau):
            continue
        
        # 3. Nombre de produits
        if str(row.get("{{Nombre_produits}}","")).strip() != nb_produits:
            continue
        
        # 4. Budget (by etape)
        etape = str(row.get("{{Etape}}","")).strip()
        if etape == "Nettoyer":
            if not budget_affordable(row.get("{{Budget}}"), budget_net):
                continue
        else:
            if not budget_affordable(row.get("{{Budget}}"), budget_sq):
                continue
        
        # 5. Product name must be valid
        product_name = str(row.get("{{Nom_produit}} ","")).strip()
        if not product_name or product_name in ["nan", "Aucun", ""]:
            continue
        
        # --- ASSIGN ---
        routine_key = str(row.get("{{Routines}}","")).strip()  # Morning / Evening
        
        if routine_key not in results:
            results[routine_key] = {}
        if etape not in results[routine_key]:
            results[routine_key][etape] = []
        
        # Build product info
        pinfo = {
            "nom":    product_name,
            "marque": str(row.get("{{Nom_marque}}","")).strip(),
            "etape":  etape,
            "routine": routine_key,
            "budget": str(row.get("{{Budget}}","")),
        }
        
        # Enrich from Fiche Produit if available
        if product_name in product_lookup:
            fp = product_lookup[product_name]
            pinfo["prix"]      = str(fp.get("{{Prix_produit}}","")).strip()
            pinfo["taille"]    = str(fp.get("{{Taille_produit}}","")).strip()
            pinfo["promesse"]  = str(fp.get("{{Promesse_produit}}","")).strip()
            pinfo["actifs"]    = str(fp.get("{Ingrédients_clés}}", "")).strip()
            pinfo["usage"]     = str(fp.get("{Usage_produit}}", "")).strip()
            pinfo["intro"]     = str(fp.get("{{Introduction_fiche}}","")).strip()
        
        # Only add first product per etape (highest priority = first match)
        if not results[routine_key].get(etape):
            results[routine_key][etape] = pinfo
    
    return {
        "type_peau":    type_peau,
        "etats_peau":   etats_peau,
        "phototype":    phototype,
        "produits":     results,
    }


# ══════════════════════════════════════════════════════════════
#  PDF GENERATION
# ══════════════════════════════════════════════════════════════
def hr(color=C_BORDER, width=1):
    return HRFlowable(width="100%", thickness=width, color=color, spaceAfter=8, spaceBefore=4)


def blush_box(content_list, padding=(8, 12)):
    """Wrap content in a blush-colored box."""
    data = [[content_list]]
    t = Table(data, colWidths=[W - 40*mm])
    t.setStyle(TableStyle([
        ("BACKGROUND",  (0,0), (-1,-1), C_BLUSH),
        ("ROUNDEDCORNERS", [8]),
        ("TOPPADDING",   (0,0), (-1,-1), padding[0]),
        ("BOTTOMPADDING",(0,0), (-1,-1), padding[0]),
        ("LEFTPADDING",  (0,0), (-1,-1), padding[1]),
        ("RIGHTPADDING", (0,0), (-1,-1), padding[1]),
    ]))
    return t


def tag_row(label, value, styles=STYLES):
    return Table(
        [[Paragraph(label, styles["label"]), Paragraph(str(value), styles["value"])]],
        colWidths=[45*mm, W - 40*mm - 45*mm - 10*mm]
    )


def product_card(pinfo, etape_num, styles=STYLES):
    """Build a product card as a Table."""
    STEP_COLORS = {
        "Nettoyer":  colors.HexColor("#b5c4d8"),
        "Traiter":   colors.HexColor("#d4877a"),
        "Hydrater":  colors.HexColor("#c8a96e"),
        "Protéger":  colors.HexColor("#a8c4a0"),
    }
    etape = pinfo.get("etape", "")
    step_color = STEP_COLORS.get(etape, C_ROSE)
    
    # Left badge
    badge_text = f"<b>{etape_num}</b><br/>{etape}"
    badge = Paragraph(badge_text, ParagraphStyle("badge", fontName="Helvetica-Bold",
        fontSize=8, textColor=C_WHITE, alignment=TA_CENTER, leading=11))
    
    badge_table = Table([[badge]], colWidths=[18*mm],
        rowHeights=[None])
    badge_table.setStyle(TableStyle([
        ("BACKGROUND",   (0,0), (-1,-1), step_color),
        ("VALIGN",       (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING",   (0,0), (-1,-1), 12),
        ("BOTTOMPADDING",(0,0), (-1,-1), 12),
        ("LEFTPADDING",  (0,0), (-1,-1), 4),
        ("RIGHTPADDING", (0,0), (-1,-1), 4),
    ]))
    
    # Right content
    nom    = pinfo.get("nom", "")
    marque = pinfo.get("marque", "")
    prix   = pinfo.get("prix", "")
    taille = pinfo.get("taille", "")
    promes = pinfo.get("promesse", "")
    actifs = pinfo.get("actifs", "")
    usage  = pinfo.get("usage", "")
    
    content_items = []
    content_items.append(Paragraph(nom, styles["product_name"]))
    content_items.append(Paragraph(marque, styles["product_brand"]))
    
    if prix and prix != "nan":
        prix_str = f"{prix} €" if "€" not in prix else prix
        content_items.append(Paragraph(f"<b>{prix_str}</b>" + (f"  ·  {taille}" if taille and taille != "nan" else ""), styles["price"]))
    
    if promes and promes != "nan":
        short_promes = promes[:200] + ("..." if len(promes) > 200 else "")
        content_items.append(Paragraph(short_promes, styles["product_body"]))
    
    if actifs and actifs != "nan":
        content_items.append(Paragraph(f"<b>Actifs clés :</b> {actifs[:150]}", styles["product_body"]))
    
    content_para = [item for item in content_items]
    
    card = Table(
        [[badge_table, content_para]],
        colWidths=[20*mm, W - 40*mm - 20*mm - 6*mm]
    )
    card.setStyle(TableStyle([
        ("BACKGROUND",   (0,0), (-1,-1), C_WHITE),
        ("BACKGROUND",   (1,0), (1,0),   C_CREAM),
        ("VALIGN",       (0,0), (-1,-1), "TOP"),
        ("TOPPADDING",   (1,0), (1,0), 10),
        ("BOTTOMPADDING",(1,0), (1,0), 10),
        ("LEFTPADDING",  (1,0), (1,0), 10),
        ("RIGHTPADDING", (1,0), (1,0), 10),
        ("LEFTPADDING",  (0,0), (0,0), 0),
        ("RIGHTPADDING", (0,0), (0,0), 0),
        ("TOPPADDING",   (0,0), (0,0), 0),
        ("BOTTOMPADDING",(0,0), (0,0), 0),
        ("BOX",          (0,0), (-1,-1), 1, C_BORDER),
        ("ROUNDEDCORNERS", [6]),
    ]))
    return card


def build_pdf(quiz, match_result, output_path):
    """Generate the full PDF guide."""
    prenom = quiz.get("prenom", "")
    nom_   = quiz.get("nom", "")
    full_name = f"{prenom} {nom_}".strip()
    
    type_peau  = match_result["type_peau"]
    etats_peau = match_result["etats_peau"]
    phototype  = match_result["phototype"]
    produits   = match_result["produits"]
    
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=20*mm, rightMargin=20*mm,
        topMargin=18*mm, bottomMargin=18*mm,
        title=f"Guide Beauté Personnalisé — {full_name}",
        author="care.on.line",
    )
    
    story = []
    S = STYLES
    
    # ── PAGE DE COUVERTURE ─────────────────────────────────────
    story.append(Spacer(1, 30*mm))
    story.append(Paragraph("CARE.ON.LINE", S["cover_brand"]))
    story.append(Spacer(1, 4*mm))
    story.append(hr(C_GOLD, 0.5))
    story.append(Spacer(1, 6*mm))
    story.append(Paragraph("Mon Guide Beauté", S["cover_title"]))
    story.append(Paragraph("Personnalisé", ParagraphStyle("cov2",
        fontName="Helvetica", fontSize=22, textColor=C_ROSE,
        alignment=TA_CENTER, spaceAfter=20)))
    story.append(Spacer(1, 10*mm))
    story.append(hr(C_BORDER, 0.5))
    story.append(Spacer(1, 8*mm))
    story.append(Paragraph(f"Créé pour {full_name}", S["cover_name"]))
    story.append(Spacer(1, 4*mm))
    story.append(Paragraph(
        f"Type de peau · {type_peau}  ·  {phototype}",
        ParagraphStyle("cov3", fontName="Helvetica", fontSize=10,
            textColor=C_MUTED, alignment=TA_CENTER, spaceAfter=4)
    ))
    
    etats_str = "  ·  ".join(etats_peau[:3])
    story.append(Paragraph(etats_str, ParagraphStyle("cov4",
        fontName="Helvetica", fontSize=9, textColor=C_MUTED,
        alignment=TA_CENTER, spaceAfter=30)))
    
    story.append(Spacer(1, 40*mm))
    story.append(Paragraph("@care.on_line", ParagraphStyle("footer_cover",
        fontName="Helvetica", fontSize=8, textColor=C_BORDER,
        alignment=TA_CENTER)))
    
    story.append(PageBreak())
    
    # ── PAGE 2 — MON ANALYSE ──────────────────────────────────
    story.append(Paragraph("MON ANALYSE", S["section_eyebrow"]))
    story.append(Paragraph("Ce que tu m'as confié", S["section_title"]))
    story.append(hr())
    story.append(Spacer(1, 4*mm))
    
    # Profile grid
    profile_data = [
        ["Prénom", prenom, "Email", quiz.get("email","")],
        ["Âge", quiz.get("age",""), "Genre", quiz.get("genre","").capitalize()],
        ["Couleur de peau", quiz.get("couleur_peau",""), "Couleur cheveux", quiz.get("couleur_cheveux","")],
        ["Préoccupation principale", quiz.get("premiere_preoccupation",""), "Phototype", phototype],
        ["Rides", quiz.get("rides",""), "Acné", quiz.get("acne","")],
        ["Stress", quiz.get("stress",""), "Tabac", quiz.get("tabac","")],
        ["Sommeil", quiz.get("sommeil",""), "Alimentation", quiz.get("alimentation","")],
    ]
    
    col_w = (W - 40*mm) / 4
    for row in profile_data:
        t = Table([
            [Paragraph(row[0], S["label"]), Paragraph(str(row[1]), S["value"]),
             Paragraph(row[2], S["label"]), Paragraph(str(row[3]), S["value"])]
        ], colWidths=[col_w]*4)
        t.setStyle(TableStyle([
            ("TOPPADDING",   (0,0),(-1,-1), 5),
            ("BOTTOMPADDING",(0,0),(-1,-1), 5),
            ("LEFTPADDING",  (0,0),(-1,-1), 6),
            ("LINEBELOW",    (0,0),(-1,-1), 0.5, C_CREAM2),
        ]))
        story.append(t)
    
    # Allergies & Mentions
    story.append(Spacer(1, 6*mm))
    allergies = quiz.get("allergies", [])
    if allergies:
        story.append(Paragraph("Allergies / Intolérances",  S["label"]))
        story.append(Paragraph("  ·  ".join(allergies), S["tag"]))
    
    mentions = quiz.get("mentions", [])
    if mentions:
        story.append(Paragraph("Mentions importantes", S["label"]))
        story.append(Paragraph("  ·  ".join(mentions), S["tag"]))
    
    story.append(PageBreak())
    
    # ── PAGE 3 — DIAGNOSTIC ───────────────────────────────────
    story.append(Paragraph("MA PRESCRIPTION", S["section_eyebrow"]))
    story.append(Paragraph("Mon Diagnostic Personnalisé", S["section_title"]))
    story.append(hr())
    story.append(Spacer(1, 3*mm))
    
    # Type de peau box
    diag_rows = [
        ["Mon type de peau",   type_peau],
        ["Mon phototype",      phototype],
    ]
    for label, val in diag_rows:
        t = Table([[
            Paragraph(label, S["label"]),
            Paragraph(f"<b>{val}</b>", ParagraphStyle("diag_val",
                fontName="Helvetica-Bold", fontSize=13, textColor=C_DEEP))
        ]], colWidths=[55*mm, W - 40*mm - 55*mm])
        t.setStyle(TableStyle([
            ("BACKGROUND",   (0,0),(-1,-1), C_CREAM),
            ("TOPPADDING",   (0,0),(-1,-1), 10),
            ("BOTTOMPADDING",(0,0),(-1,-1), 10),
            ("LEFTPADDING",  (0,0),(-1,-1), 12),
            ("BOX",          (0,0),(-1,-1), 1, C_BORDER),
            ("LINEBELOW",    (0,0),(-1,-1), 0, C_WHITE),
        ]))
        story.append(t)
        story.append(Spacer(1, 2*mm))
    
    # États de peau
    story.append(Spacer(1, 4*mm))
    story.append(Paragraph("L'état de ma peau", S["h2"]))
    
    for etat in etats_peau:
        t = Table([[
            Paragraph(etat, ParagraphStyle("etat_name", fontName="Helvetica-Bold",
                fontSize=11, textColor=C_ROSE))
        ]], colWidths=[W - 40*mm])
        t.setStyle(TableStyle([
            ("BACKGROUND",   (0,0),(-1,-1), C_BLUSH),
            ("TOPPADDING",   (0,0),(-1,-1), 8),
            ("BOTTOMPADDING",(0,0),(-1,-1), 8),
            ("LEFTPADDING",  (0,0),(-1,-1), 14),
            ("BOX",          (0,0),(-1,-1), 1, C_BORDER),
        ]))
        story.append(t)
        story.append(Spacer(1, 2*mm))
    
    story.append(PageBreak())
    
    # ── PAGES ROUTINE ─────────────────────────────────────────
    for routine_key, label in [("Morning", "Routine Matin"), ("Evening", "Routine Soir")]:
        routine_color = colors.HexColor("#f7e8c8") if routine_key == "Morning" else colors.HexColor("#dde3f0")
        
        story.append(Paragraph("MON PROTOCOLE BEAUTÉ", S["section_eyebrow"]))
        story.append(Paragraph(label, S["section_title"]))
        story.append(hr(C_GOLD if routine_key == "Morning" else C_ROSE))
        story.append(Spacer(1, 4*mm))
        
        routine_products = produits.get(routine_key, {})
        
        # Step order
        etape_order = ["Nettoyer", "Traiter", "Hydrater", "Protéger"]
        etape_num = 1
        
        has_products = False
        for etape in etape_order:
            pinfo = routine_products.get(etape)
            if pinfo and isinstance(pinfo, dict):
                has_products = True
                story.append(KeepTogether([
                    product_card(pinfo, etape_num),
                    Spacer(1, 4*mm)
                ]))
                etape_num += 1
        
        if not has_products:
            story.append(Paragraph(
                "Aucun produit trouvé pour cette routine avec les critères sélectionnés.",
                S["body_muted"]
            ))
        
        story.append(PageBreak())
    
    # ── SHOPPING LIST ──────────────────────────────────────────
    story.append(Paragraph("MA SHOPPING LIST", S["section_eyebrow"]))
    story.append(Paragraph("Récapitulatif Beauté", S["section_title"]))
    story.append(hr())
    story.append(Spacer(1, 4*mm))
    
    all_products = {}
    for routine_key in ["Morning", "Evening"]:
        for etape_order in ["Nettoyer", "Traiter", "Hydrater", "Protéger"]:
            p = produits.get(routine_key, {}).get(etape_order)
            if p and isinstance(p, dict):
                key = p.get("nom","")
                if key and key not in all_products:
                    all_products[key] = p
    
    if all_products:
        table_data = [
            [Paragraph("Produit", S["label"]),
             Paragraph("Marque", S["label"]),
             Paragraph("Étape", S["label"]),
             Paragraph("Prix", S["label"])]
        ]
        for pinfo in all_products.values():
            prix = pinfo.get("prix","")
            prix_str = f"{prix} €" if prix and prix != "nan" and "€" not in prix else (prix or "—")
            table_data.append([
                Paragraph(pinfo.get("nom",""), S["body"]),
                Paragraph(pinfo.get("marque",""), S["body_muted"]),
                Paragraph(pinfo.get("etape",""), S["tag"]),
                Paragraph(prix_str, S["price"]),
            ])
        
        col_widths = [W*0.42 - 20*mm, W*0.25 - 10*mm, W*0.18 - 5*mm, W*0.15 - 5*mm]
        t = Table(table_data, colWidths=col_widths)
        t.setStyle(TableStyle([
            ("BACKGROUND",   (0,0), (-1,0), C_CREAM2),
            ("ROWBACKGROUNDS",(0,1),(-1,-1), [C_WHITE, C_CREAM]),
            ("TOPPADDING",   (0,0),(-1,-1), 8),
            ("BOTTOMPADDING",(0,0),(-1,-1), 8),
            ("LEFTPADDING",  (0,0),(-1,-1), 8),
            ("LINEBELOW",    (0,0),(-1,-1), 0.5, C_BORDER),
            ("BOX",          (0,0),(-1,-1), 1, C_BORDER),
        ]))
        story.append(t)
    else:
        story.append(Paragraph("Aucun produit à afficher.", S["body_muted"]))
    
    # Footer note
    story.append(Spacer(1, 12*mm))
    story.append(hr(C_GOLD, 0.5))
    story.append(Spacer(1, 4*mm))
    story.append(Paragraph(
        "Ce guide a été personnalisé exclusivement pour toi par care.on.line. "
        "Les produits recommandés ont été sélectionnés en fonction de ton profil beauté unique. "
        "Pour toute question, contacte ton dermo-expert.",
        ParagraphStyle("footer_note", fontName="Helvetica", fontSize=8,
            textColor=C_MUTED, alignment=TA_CENTER, leading=13)
    ))
    story.append(Spacer(1, 4*mm))
    story.append(Paragraph("@care.on_line  ·  care.on.line",
        ParagraphStyle("footer_brand", fontName="Helvetica-Bold", fontSize=9,
            textColor=C_GOLD, alignment=TA_CENTER)))
    
    # ── BUILD ──────────────────────────────────────────────────
    def on_page(canvas, doc):
        canvas.saveState()
        # Top accent bar
        canvas.setFillColor(C_GOLD)
        canvas.rect(0, H - 3, W, 3, fill=1, stroke=0)
        # Page number (skip cover)
        if doc.page > 1:
            canvas.setFont("Helvetica", 7)
            canvas.setFillColor(C_MUTED)
            canvas.drawCentredString(W/2, 10*mm, f"— {doc.page} —")
        canvas.restoreState()
    
    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    print(f"✅ PDF généré : {output_path}")
    return output_path


# ══════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════
def run(quiz_data, excel_path, output_path):
    # Load Excel
    print("📊 Chargement des données produits...")
    df_routine  = pd.read_excel(excel_path, sheet_name="Routine", header=0)
    df_fp_raw   = pd.read_excel(excel_path, sheet_name="Fiche Produit", header=0)
    df_products = df_fp_raw.copy()
    df_products.columns = df_fp_raw.iloc[0]
    df_products = df_products[1:].reset_index(drop=True)
    
    print("🔍 Analyse du profil...")
    print(f"   Préoccupation : {quiz_data.get('premiere_preoccupation')}")
    print(f"   Type peau    : {derive_type_peau(quiz_data)}")
    print(f"   Etats peau   : {derive_etats_peau(quiz_data)}")
    print(f"   Phototype    : {derive_phototype(quiz_data)}")
    
    print("🌸 Matching des produits...")
    result = match_products(quiz_data, df_routine, df_products)
    
    # Print matched products
    for rk in ["Morning", "Evening"]:
        print(f"\n  ── {rk} ──")
        for etape, p in result["produits"].get(rk, {}).items():
            if isinstance(p, dict):
                print(f"     {etape}: {p['nom']} ({p['marque']})")
    
    print("\n📄 Génération du PDF...")
    build_pdf(quiz_data, result, output_path)
    return result


if __name__ == "__main__":
    # Sample quiz data matching the example profile from the PDF
    # (peau sèche, déshydratée, sensible, mature, cernes, phototype 3)
    sample_quiz = {
        "prenom": "Sophie",
        "nom": "Martin",
        "email": "sophie.martin@email.com",
        "age": "42",
        "genre": "femme",
        "maternite": "non",
        # Visage
        "couleur_cheveux":  "Chatain",
        "couleur_peau":     "Claire",
        "couleur_yeux":     "Noisettes/Marrons",
        "apres_bain_soleil":"Phototype 3",
        "rides":            "Ridules naissantes",
        "apres_creme":      "Peau sèche",
        "apres_douche":     "Peau sèche",
        "reactions_peau":   "Peau réactive",
        "reaction_sport":   "Peau non réactive",
        "acne":             "Pas d'acné",
        "traitement_dermato": "Non",
        "hyperpigmentation":  "Non",
        # Mode de vie
        "tabac":            "Non",
        "exposition_soleil":"Moyenne",
        "pollution_air":    "Modérée",
        "exposition_autre": ["Eau calcaire", "Chauffage électrique"],
        "stress":           "Par période",
        "sport":            "Une fois par semaine",
        "eau":              "Plusieurs fois par jour",
        "sommeil":          "Bien",
        "alimentation":     "Équilibré",
        "allergies":        [],
        # Préoccupations
        "premiere_preoccupation": "Mes cernes",
        # Routines
        "nombre_produits":  "3 produits",
        "rituel":           ["Une crème", "Un sérum", "Un contour des yeux"],
        "rituel_eau":       "Avec de l'eau",
        "creme_texture":    "Onctueuse",
        "demaquillage_texture": "Lait",
        "maquillage":       "De temps en temps",
        "applications":     "Parfois",
        # Préférences
        "budget_nettoyant":         "Entre 10 et 29 €",
        "budget_soin_quotidien":    "Entre 30 et 69 €",
        "budget_soin_specifique":   "Entre 30 et 69 €",
        "budget_accessoire":        "Entre 10 et 29 €",
        "circuit_achats":   ["Parapharmacie/pharmacie", "E-shop"],
        "mentions":         ["Clean", "Fabriqué en France"],
        "criteres":         ["L'efficacité du produit", "La composition", "Le prix"],
        "marques_preferees":"Caudalie, Avène, Garancia",
    }
    
    excel_path  = "/mnt/user-data/uploads/Data_produits.xlsx"
    output_path = "/mnt/user-data/outputs/guide_beaute_sophie.pdf"
    
    run(sample_quiz, excel_path, output_path)
