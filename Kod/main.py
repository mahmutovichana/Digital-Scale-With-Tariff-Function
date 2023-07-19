import time
import ST7735
import math
import sys
from machine import Pin, SPI, Timer
from micropython import schedule
from ST7735 import TFT
from sysfont import sysfont
from hx711 import HX711
from utime import sleep_us

# Konstante za promjenu prikaza na TFT-u
SCREEN_WIDTH = 128
SCREEN_HEIGHT = 160

# Definiranje pinova za ulaze i izlaze matrice tipkovnice
ulazi = [Pin(21, Pin.IN, Pin.PULL_DOWN), Pin(22, Pin.IN, Pin.PULL_DOWN), Pin(26, Pin.IN, Pin.PULL_DOWN), Pin(27, Pin.IN, Pin.PULL_DOWN)]
izlazi = [Pin(0, Pin.OUT), Pin(1, Pin.OUT), Pin(2, Pin.OUT), Pin(3, Pin.OUT)]

# Inicijalizacija TFT zaslona
spi = SPI(0, baudrate=62500000, polarity=0, phase=0, sck=Pin(18), mosi=Pin(19), miso=Pin(16))
tft = TFT(spi, 15, 20, 17)
tft.initr()
tft.rgb(True)

# Definiranje matrice tipki
tipke = [
    ['1', '2', '3', 'X'],
    ['4', '5', '6', 'X'],
    ['7', '8', '9', 'X'],
    ['X', '0', '#', 'X']
]

# Boje koristene u sistemu
black = TFT.BLACK
white = TFT.WHITE
red = TFT.RED

# Mapa koja povezuje brojeve s imenima artikala
mapa_artikala = [
    ('1', 'Limun', 1.5),
    ('2', 'Jabuka', 2.0),
    ('3', 'Banana', 0.7),
    ('4', 'Naranca', 1.2),
    ('5', 'Kruska', 1.8),
    ('6', 'Ananas', 4.5),
    ('7', 'Mango', 2.7),
    ('8', 'Grozdje', 3.2),
    ('9', 'Breskva', 2.0),
    ('0', 'Sljiva', 1.0)
]

def print_refreshing_text(prevText, text, height, color=white, size=1.7, nowrap=True):
    # Izbriši prethodni ispis zamračivanjem
    tft.text((0, height), str(prevText), black, sysfont, size, nowrap)
    # Ispisi novu vrijednost
    tft.text((0, height), text, color, sysfont, size, nowrap)

def print_dobroslicu():
    tft.fill(TFT.CYAN)
    v = 37
    offset = sysfont["Width"]
    rijeci = [" Dobrodosli", " na nasu", " digitalnu", " vagu"]
    
    for rijec in rijeci:
        tft.text((0, v+offset), rijec, black, sysfont, 2, nowrap=True)
        offset += sysfont["Width"] * 4

def print_uputstva():
    tft.fill(TFT.CYAN)
    v = 15
    offset = sysfont["Width"]
    rijeci = [" Pritisnite", " #", " za ponovni", " pregled", " spiska", " artikala"]
    
    for rijec in rijeci:
        tft.text((0, v+offset), rijec, black, sysfont, 1.9, nowrap=True)
        offset += sysfont["Width"] * 4

def print_mapu_artikala():
    tft.fill(TFT.CYAN)
    v = 0
    v += sysfont["Width"]
    tft.text((0, v), "Spisak(KM/kg)", black, sysfont, 1.75, nowrap=True)
    v += sysfont["Width"] * 1.5
    
    # Pronalaženje najdužeg naziva
    max_duzina = max(len(item[1]) for item in mapa_artikala)
    
    for item in mapa_artikala:
        v += sysfont["Height"] * 1.65
        naziv = item[1]
        cijena = item[2]
        cijena_text = "{:.2f}".format(cijena)
        padding = ' ' * (max_duzina - len(naziv))
        tft.text((0, v), naziv + padding + " - " + cijena_text, black, sysfont, 1.75, nowrap=True)

def print_podatke_artikla(artikal):
    ime_artikla = None
    cijena_artikla = None

    for item in mapa_artikala:
        if item[0] == artikal:
            ime_artikla = item[1]
            cijena_artikla = item[2]
            break
    
    tft.fill(TFT.BLACK)
    v = 10
    v += sysfont["Width"]
    
    tft.text((0, v), "Artikal:", white, sysfont, 1.75, nowrap=True)
    v += sysfont["Width"] * 3
    tft.text((0, v), f"{ime_artikla or 'Nepoznat'}", white, sysfont, 1.75, nowrap=True)
    
    v += sysfont["Width"] * 4.5
    
    tft.text((0, v), "Cijena (g):", white, sysfont, 1.75, nowrap=True)
    v += sysfont["Width"] * 3
    tft.text((0, v), f"{cijena_artikla or 'Nepoznat'}", white, sysfont, 1.75, nowrap=True)
    
    v += sysfont["Width"] * 4.5
    
    tft.text((0, v), "Tezina (g):", white, sysfont, 1.6, nowrap=True)
    
    v += sysfont["Width"] * 6.5
    
    tft.text((0, v), "Ukupna cijena:", white, sysfont, 1.6, nowrap=True)
    
    ukupna_cijena = None

    return ime_artikla, cijena_artikla, v

def prepoznaj_artikal(artikal):
    
    ime_artikla, cijena_artikla, v = print_podatke_artikla(artikal)
    
    if ime_artikla is not None:
        print("Artikal:", ime_artikla)
    else:
        print("Nepoznat artikal")
    
    if cijena_artikla is not None:
        print("Cijena (kg):", cijena_artikla)
    else:
        print("Nepoznata cijena")
    
    return ime_artikla, cijena_artikla, v

print_dobroslicu()
time.sleep(3)
print_uputstva()
time.sleep(3)
print_mapu_artikala()
time.sleep(5)
ime_artikla, cijena_artikla, v = prepoznaj_artikal('X')
ukupna_cijena = 0

prethodno_vrijeme = time.time()
vrijeme_azuriranja = 0.1  # Vrijeme u sekundama između svakog ažuriranja prikaza
prethodna_vrijednost = 0 # vrijednost od senzora
prethodna_cijena = 0 # vrijednost od cijene
cijena_artikla = None
ime_artikla = None

def unos_tastature():
    global ime_artikla, cijena_artikla
# Postaviti sve izlaze na LOW (0V)
    for izlaz in izlazi:
        izlaz.value(0)

    # Provjeriti koje tipke su pritisnute
    for i in range(len(ulazi)):
        # Postaviti trenutni izlaz na HIGH (3.3V)
        izlazi[i].value(1)

        # Provjerite ulaze i pronađite pritisnutu tipku
        for j in range(len(ulazi)):
            if ulazi[j].value() == 1:
                if ulazi[j].value() == 1:
                    print(tipke[j][i])
                    if tipke[j][i] == "#":
                        # Pritisnuta je tipka "#", izvrši akciju povratka na početni zaslon
                        print_mapu_artikala()
                        time.sleep(3)
                        ime_artikla, cijena_artikla, v = prepoznaj_artikal('X')
                        ukupna_cijena = 0
                    else:
                        ime_artikla, cijena_artikla, v = prepoznaj_artikal(tipke[j][i])

        # Postaviti trenutni izlaz natrag na LOW (0V)
        izlazi[i].value(0)

# Dodavanje Timer-a za periodično izvršavanje funkcije unos_tastature
t = Timer(period=10, callback=lambda t: unos_tastature())

# Poziv metode calibrate za kalibraciju
scale = HX711(d_out=9, pd_sck=8)
reference_units = 100  # Referentna vrijednost u jedinicama mjere (npr. kilogrami)
scales_value = 0  # Inicijalizacija sirove vrijednosti s 0

calibration_factor = scale.calibrate(reference_units, scales_value)  # Kalibracija s početnom težinom 0
print("Calibration factor:", calibration_factor)

# Glavna petlja
while True:
    
    trenutno_vrijeme = time.time()
    
    # Očitavanje i ažuriranje težine
    scales_value = scale.read(raw=True)
    trenutna_vrijednost = abs(scales_value * calibration_factor  - reference_units) # Računanje težine na temelju kalibracijskog faktora
    print("Weight:", trenutna_vrijednost, "g")
    
    if cijena_artikla is not None:
        ukupna_cijena = (cijena_artikla * trenutna_vrijednost) 

    if trenutno_vrijeme - prethodno_vrijeme >= vrijeme_azuriranja:
        
        prethodno_vrijeme = trenutno_vrijeme
      
        if trenutna_vrijednost != prethodna_vrijednost:
            # Ažurirati prikaz samo ako se vrijednost promijenila
            print_refreshing_text("{:.3f}".format(prethodna_vrijednost), "{:.3f}".format(trenutna_vrijednost), v - sysfont["Width"] * 3.4)
            prethodna_vrijednost = trenutna_vrijednost
        
        if prethodna_cijena != ukupna_cijena:
            # Ažurirati prikaz samo ako se vrijednost promijenila
            print_refreshing_text("{:.3f}".format(prethodna_cijena)+" KM", "{:.3f}".format(ukupna_cijena)+" KM", v + sysfont["Width"] * 3)
            prethodna_cijena = ukupna_cijena
        
    # Ispisati novu vrijednost težine i cijene
    print_refreshing_text("{:.3f}".format(prethodna_vrijednost), "{:.3f}".format(trenutna_vrijednost), v - sysfont["Width"] * 3.4)
    print_refreshing_text("{:.3f}".format(prethodna_cijena)+" KM", "{:.3f}".format(ukupna_cijena)+" KM", v + sysfont["Width"] * 3)
    
    

