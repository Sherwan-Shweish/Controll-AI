"""RheinMain-Stammdaten: Schlüssel unverändert aus der VarianceAI-Referenz."""

BUCHUNGSKREIS = "1000"
REGIONEN = (("NORD", "Nord", 1.0), ("SUED", "Süd", 1.2), ("WEST", "West", 0.9))
PRODUKTGRUPPEN = (("ANT", "Antriebe"), ("STE", "Steuerungen"), ("SEN", "Sensorik"))
MATERIALIEN = [
    ("ANT100", "Getriebemotor GM 100", "ANT", 120000, 56000, 300),
    ("ANT200", "Getriebemotor GM 200", "ANT", 210000, 92000, 180),
    ("ANT300", "Servoantrieb SA 300", "ANT", 340000, 145000, 90),
    ("STE10", "Steuerung Basic C10", "STE", 85000, 56000, 220),
    ("STE20", "Steuerung Pro C20", "STE", 190000, 78000, 160),
    ("STE30", "Steuerung Edge C30", "STE", 280000, 110000, 90),
    ("SEN01", "Drucksensor P1", "SEN", 14000, 6000, 1500),
    ("SEN02", "Temperatursensor T2", "SEN", 9500, 4000, 2000),
    ("SEN03", "Näherungssensor N3", "SEN", 12000, 5000, 1600),
    ("SENX1", "Smart Sensor X1", "SEN", 26000, 12000, 380),
]
KUNDEN = (
    ("K101", "Hanse Fördertechnik GmbH", "NORD"),
    ("K102", "Weser Anlagenbau AG", "NORD"),
    ("K103", "Elbe Automation KG", "NORD"),
    ("K104", "Nordwind Maschinen GmbH", "NORD"),
    ("K201", "Alpen Antriebstechnik GmbH", "SUED"),
    ("K202", "Neckar Werkzeugmaschinen AG", "SUED"),
    ("K203", "Isar Robotics GmbH", "SUED"),
    ("K204", "Bodensee Verpackungstechnik KG", "SUED"),
    ("K301", "Rheinland Industrieanlagen GmbH", "WEST"),
    ("K302", "Ruhr Stahlbau AG", "WEST"),
    ("K303", "Mosel Prozesstechnik GmbH", "WEST"),
    ("K304", "Eifel Fördersysteme KG", "WEST"),
)
KOSTENSTELLEN = [
    (
        "4100",
        "Gießerei",
        "PC-FERT",
        10000,
        (("410000", 120, 24), ("400000", 20, 210), ("430000", 1, 4500)),
        (("435000", 9000000), ("480000", 13000000)),
    ),
    (
        "4200",
        "Montage",
        "PC-FERT",
        8000,
        (("400000", 12, 500), ("430000", 1, 4200), ("410000", 10, 24)),
        (("435000", 7000000), ("480000", 8000000)),
    ),
    (
        "4300",
        "Lackiererei",
        "PC-FERT",
        4000,
        (("400000", 3, 1200), ("410000", 30, 24), ("430000", 1, 4000)),
        (("435000", 6000000), ("480000", 14000000)),
    ),
    (
        "4400",
        "Instandhaltung",
        "PC-SERV",
        3000,
        (("430000", 1, 4800), ("400000", 2, 400)),
        (("435000", 5000000), ("470000", 4000000)),
    ),
    (
        "4500",
        "Qualitätssicherung",
        "PC-SERV",
        2500,
        (("430000", 1, 5000), ("410000", 5, 24)),
        (("435000", 4500000), ("480000", 1500000)),
    ),
]
