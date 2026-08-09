"""Reference data: qualification catalogue, functions and compliance templates.

This is deliberately a catalogue and not a set of hard-coded rules. Everything
here is seeded once and then editable in the application - a branch that needs
another qualification adds it, a function that needs another certificate gets a
requirement. The seed only guarantees that a fresh (or upgraded) installation
starts with the obligations a German branch of this trade actually has, instead
of an empty screen the manager has to fill from memory.

The fixed ids matter: migration `0004` writes the same ids when it moves the
dates out of `employee_profiles`, so seeding afterwards updates those rows
rather than creating duplicates.
"""

from dataclasses import dataclass, field


# Qualification categories, used for grouping in the UI.
CATEGORY_LICENCE = "licence"
CATEGORY_TRAINING = "training"
CATEGORY_MEDICAL = "medical"
CATEGORY_INSTRUCTION = "instruction"

# Codes referenced from code (cross-checks, migrations). Everything else is
# looked up by id or code at runtime.
CODE_DRIVER_LICENCE = "fuehrerschein"
CODE_DRIVER_LICENCE_CHECK = "fuehrerschein_kontrolle"
CODE_FIRST_AID = "erste_hilfe"
CODE_IPAF = "ipaf"
CODE_INSTRUCTION = "unterweisung_allgemein"
CODE_OCCUPATIONAL_HEALTH = "arbeitsmedizin"


@dataclass(frozen=True)
class QualificationTypeSeed:
    id: str
    code: str
    name: str
    category: str
    validity_months: int | None
    reminder_days: int
    evidence_required: bool
    legal_basis: str | None = None
    description: str | None = None


QUALIFICATION_TYPES: tuple[QualificationTypeSeed, ...] = (
    QualificationTypeSeed(
        id="qt-fuehrerschein",
        code=CODE_DRIVER_LICENCE,
        name="Fahrerlaubnis",
        category=CATEGORY_LICENCE,
        validity_months=None,
        reminder_days=60,
        evidence_required=True,
        legal_basis="FeV",
        description="Vorhandene Fahrerlaubnisklassen. Ohne eigene Frist; die Klassen C/CE sind gesondert zu befristen.",
    ),
    QualificationTypeSeed(
        id="qt-fuehrerschein-kontrolle",
        code=CODE_DRIVER_LICENCE_CHECK,
        name="Fuehrerscheinkontrolle",
        category=CATEGORY_LICENCE,
        validity_months=6,
        reminder_days=30,
        evidence_required=True,
        legal_basis="DGUV Vorschrift 70 / Halterhaftung StVG",
        description="Halbjaehrliche Sichtkontrolle der Fahrerlaubnis durch die Niederlassungsleitung.",
    ),
    QualificationTypeSeed(
        id="qt-erste-hilfe",
        code=CODE_FIRST_AID,
        name="Erste-Hilfe-Ausbildung",
        category=CATEGORY_TRAINING,
        validity_months=24,
        reminder_days=60,
        evidence_required=True,
        legal_basis="DGUV Vorschrift 1 Paragraf 26",
        description="Ausbildung oder Fortbildung zum betrieblichen Ersthelfer.",
    ),
    QualificationTypeSeed(
        id="qt-ipaf",
        code=CODE_IPAF,
        name="IPAF-Bedienerschulung",
        category=CATEGORY_TRAINING,
        validity_months=60,
        reminder_days=90,
        evidence_required=True,
        legal_basis="DGUV Grundsatz 308-008",
        description="Bedienerschulung Hubarbeitsbuehnen, Kategorien 3a/3b.",
    ),
    QualificationTypeSeed(
        id="qt-psa-absturz",
        code="psa_absturz",
        name="PSA gegen Absturz",
        category=CATEGORY_INSTRUCTION,
        validity_months=12,
        reminder_days=45,
        evidence_required=True,
        legal_basis="DGUV Regel 112-198",
        description="Jaehrliche Unterweisung mit praktischer Uebung zur persoenlichen Schutzausruestung gegen Absturz.",
    ),
    QualificationTypeSeed(
        id="qt-unterweisung",
        code=CODE_INSTRUCTION,
        name="Jaehrliche Unterweisung",
        category=CATEGORY_INSTRUCTION,
        validity_months=12,
        reminder_days=45,
        evidence_required=True,
        legal_basis="ArbSchG Paragraf 12 / DGUV Vorschrift 1 Paragraf 4",
        description="Allgemeine Sicherheitsunterweisung, jaehrlich zu wiederholen.",
    ),
    QualificationTypeSeed(
        id="qt-arbeitsmedizin",
        code=CODE_OCCUPATIONAL_HEALTH,
        name="Arbeitsmedizinische Vorsorge",
        category=CATEGORY_MEDICAL,
        validity_months=36,
        reminder_days=60,
        evidence_required=True,
        legal_basis="ArbMedVV",
        description="Pflicht- oder Angebotsvorsorge, je nach Taetigkeit (u. a. G41 Absturzgefahr).",
    ),
    QualificationTypeSeed(
        id="qt-befaehigte-person",
        code="befaehigte_person",
        name="Befaehigte Person zur Pruefung",
        category=CATEGORY_TRAINING,
        validity_months=36,
        reminder_days=90,
        evidence_required=True,
        legal_basis="BetrSichV / TRBS 1203",
        description="Qualifikation zur Pruefung von Arbeitsmitteln, regelmaessige Fortbildung erforderlich.",
    ),
    QualificationTypeSeed(
        id="qt-brandschutzhelfer",
        code="brandschutzhelfer",
        name="Brandschutzhelfer",
        category=CATEGORY_TRAINING,
        validity_months=36,
        reminder_days=60,
        evidence_required=True,
        legal_basis="ASR A2.2 / DGUV Information 205-023",
        description="Ausbildung zum Brandschutzhelfer, Auffrischung alle drei bis fuenf Jahre.",
    ),
)


@dataclass(frozen=True)
class JobRoleSeed:
    id: str
    name: str
    description: str
    # (qualification type id, mandatory)
    requirements: tuple[tuple[str, bool], ...] = field(default_factory=tuple)


JOB_ROLES: tuple[JobRoleSeed, ...] = (
    JobRoleSeed(
        id="jr-projektleiter",
        name="Projektleiter",
        description="Fuehrt Projekte, koordiniert Montage und Service, ist auf Baustellen unterwegs.",
        requirements=(
            ("qt-unterweisung", True),
            ("qt-fuehrerschein", True),
            ("qt-fuehrerschein-kontrolle", True),
            ("qt-arbeitsmedizin", True),
            ("qt-ipaf", False),
            ("qt-erste-hilfe", False),
            ("qt-brandschutzhelfer", False),
        ),
    ),
    JobRoleSeed(
        id="jr-service-techniker",
        name="Service-Techniker",
        description="Wartung, Pruefung und Instandsetzung beim Kunden, ueberwiegend im Aussendienst.",
        requirements=(
            ("qt-unterweisung", True),
            ("qt-fuehrerschein", True),
            ("qt-fuehrerschein-kontrolle", True),
            ("qt-ipaf", True),
            ("qt-psa-absturz", True),
            ("qt-arbeitsmedizin", True),
            ("qt-befaehigte-person", True),
            ("qt-erste-hilfe", False),
        ),
    ),
    JobRoleSeed(
        id="jr-monteur",
        name="Monteur",
        description="Montage und Demontage vor Ort, Arbeiten in Hoehe mit Hubarbeitsbuehne.",
        requirements=(
            ("qt-unterweisung", True),
            ("qt-ipaf", True),
            ("qt-psa-absturz", True),
            ("qt-arbeitsmedizin", True),
            ("qt-fuehrerschein", False),
            ("qt-fuehrerschein-kontrolle", False),
            ("qt-erste-hilfe", False),
        ),
    ),
)


@dataclass(frozen=True)
class ComplianceTemplate:
    """A standard branch obligation, offered when creating a compliance record.

    Kept as reference data in code rather than a table: the manager picks one
    and gets an editable record, so nothing here has to be user-maintained.
    """

    key: str
    title: str
    category: str
    control_type: str
    recurrence: str
    legal_basis: str
    priority: str
    risk_if_missing: str


COMPLIANCE_TEMPLATES: tuple[ComplianceTemplate, ...] = (
    ComplianceTemplate(
        key="gefaehrdungsbeurteilung",
        title="Gefaehrdungsbeurteilung erstellen und fortschreiben",
        category="risk_assessment",
        control_type="document",
        recurrence="yearly",
        legal_basis="ArbSchG Paragraf 5, Paragraf 6",
        priority="critical",
        risk_if_missing="Bussgeld, persoenliche Haftung der Fuehrungskraft, kein Versicherungsschutz bei Unfall.",
    ),
    ComplianceTemplate(
        key="unterweisung_jaehrlich",
        title="Jaehrliche Sicherheitsunterweisung aller Beschaeftigten",
        category="training_instruction",
        control_type="training",
        recurrence="yearly",
        legal_basis="ArbSchG Paragraf 12, DGUV Vorschrift 1 Paragraf 4",
        priority="critical",
        risk_if_missing="Unterweisungsnachweis fehlt bei Unfalluntersuchung; Organisationsverschulden.",
    ),
    ComplianceTemplate(
        key="dguv_v3_ortsveraenderlich",
        title="Pruefung ortsveraenderlicher elektrischer Betriebsmittel",
        category="electrical_safety",
        control_type="inspection",
        recurrence="yearly",
        legal_basis="DGUV Vorschrift 3, TRBS 1201",
        priority="high",
        risk_if_missing="Elektrische Gefaehrdung; Pruefplakette fehlt bei Kundenaudit.",
    ),
    ComplianceTemplate(
        key="leitern_tritte",
        title="Pruefung von Leitern und Tritten",
        category="tools_and_equipment_inspection",
        control_type="inspection",
        recurrence="yearly",
        legal_basis="BetrSichV Paragraf 14, DGUV Information 208-016",
        priority="medium",
        risk_if_missing="Absturzgefahr, defekte Arbeitsmittel bleiben im Einsatz.",
    ),
    ComplianceTemplate(
        key="hubarbeitsbuehne_pruefung",
        title="Wiederkehrende Pruefung der Hubarbeitsbuehnen",
        category="tools_and_equipment_inspection",
        control_type="inspection",
        recurrence="yearly",
        legal_basis="BetrSichV Paragraf 14, DGUV Grundsatz 308-002",
        priority="critical",
        risk_if_missing="Einsatzverbot des Geraets, Haftung bei Personenschaden.",
    ),
    ComplianceTemplate(
        key="erste_hilfe_organisation",
        title="Erste-Hilfe-Organisation und Ersthelferquote",
        category="first_aid",
        control_type="process",
        recurrence="yearly",
        legal_basis="DGUV Vorschrift 1 Paragraf 24 bis 28",
        priority="high",
        risk_if_missing="Zu wenige Ersthelfer, Verbandkasten ueberfaellig, Meldekette unklar.",
    ),
    ComplianceTemplate(
        key="brandschutz",
        title="Brandschutzhelfer benennen und Feuerloescher pruefen",
        category="documentation",
        control_type="inspection",
        recurrence="yearly",
        legal_basis="ASR A2.2, DGUV Information 205-023",
        priority="high",
        risk_if_missing="Keine benannten Brandschutzhelfer; Loescher ohne gueltige Pruefung.",
    ),
    ComplianceTemplate(
        key="arbeitsmedizinische_vorsorge",
        title="Arbeitsmedizinische Vorsorge organisieren",
        category="occupational_health",
        control_type="medical",
        recurrence="yearly",
        legal_basis="ArbMedVV, DGUV Vorschrift 1 Paragraf 2",
        priority="high",
        risk_if_missing="Pflichtvorsorge nicht angeboten; Einsatz ohne Eignungsnachweis.",
    ),
    ComplianceTemplate(
        key="regalpruefung",
        title="Jaehrliche Regalpruefung im Lager",
        category="tools_and_equipment_inspection",
        control_type="inspection",
        recurrence="yearly",
        legal_basis="DGUV Regel 108-007, DIN EN 15635",
        priority="medium",
        risk_if_missing="Beschaedigte Regale bleiben in Nutzung; Einsturzgefahr.",
    ),
    ComplianceTemplate(
        key="fuehrerscheinkontrolle_prozess",
        title="Halbjaehrliche Fuehrerscheinkontrolle dokumentieren",
        category="documentation",
        control_type="process",
        recurrence="quarterly",
        legal_basis="StVG Paragraf 21, DGUV Vorschrift 70 Paragraf 57",
        priority="high",
        risk_if_missing="Halterhaftung bei Fahren ohne Fahrerlaubnis.",
    ),
)
