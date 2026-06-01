SmartBin - Έξυπνοι Κάδοι Απορριμμάτων
Αυτό το αποθετήριο περιέχει τον κώδικα και τις οδηγίες εγκατάστασης για το project SmartBin. Η εφαρμογή χρησιμοποιεί ένα Raspberry Pi ως edge device, έναν MQTT Broker (Mosquitto) για την ανταλλαγή μηνυμάτων, Docker για την εκτέλεση των υπηρεσιών και το Home Assistant για το τελικό User Interface (Dashboard).
Πίνακας Περιεχομένων
1.	Προαπαιτούμενα
2.	Βήμα 1: Αρχική Σύνδεση & Λήψη Κώδικα
3.	Βήμα 2: Εγκατάσταση & Ρύθμιση MQTT Broker
4.	Βήμα 3: Εγκατάσταση Docker
5.	Βήμα 4: Εγκατάσταση Home Assistant
6.	Βήμα 5: Σύνδεση Home Assistant με MQTT
7.	Βήμα 6: Εκκίνηση της Εφαρμογής SmartBin
8.	Βήμα 7: Εγκατάσταση HACS στο Home Assistant
9.	Βήμα 8: Προσθήκη Custom Καρτών (Frontend)
10.	Βήμα 9: Δημιουργία του Custom Dashboard
11.	Βήμα 10: Ρύθμιση Helpers (configuration.yaml)
Προαπαιτούμενα
●	Ένα Raspberry Pi συνδεδεμένο στο δίκτυο (ή άλλο Linux μηχάνημα/VM).
●	Γνώση της IP διεύθυνσης του Raspberry Pi.
●	Πρόσβαση στο διαδίκτυο από το Raspberry Pi.
Βήμα 1: Αρχική Σύνδεση & Λήψη Κώδικα
1.	Συνδεθείτε στο Raspberry Pi μέσω SSH ανοίγοντας ένα τερματικό στον υπολογιστή σας:
ssh <user>@<pi-ip>

(Όπου <user> είναι το όνομα χρήστη, π.χ. pi, και <pi-ip> η IP διεύθυνση του Raspberry Pi).
2.	Κατεβάστε το αποθετήριο του κώδικα (git repository) με την παρακάτω εντολή:
git clone [https://github.com/michalis003/SmartBin.git](https://github.com/michalis003/SmartBin.git)
cd SmartBin

Βήμα 2: Εγκατάσταση & Ρύθμιση MQTT Broker (Mosquitto)
Ο MQTT broker είναι υπεύθυνος για την επικοινωνία των αισθητήρων.
1.	Κάντε αναβάθμιση και εγκαταστήστε το Mosquitto:
sudo apt-get update
sudo apt-get install -y mosquitto mosquitto-clients

2.	Επιβεβαιώστε ότι τρέχει σωστά:
systemctl status mosquitto

Πρέπει να δείτε το μήνυμα Active: active (running). Ο broker ακούει στην προεπιλεγμένη θύρα 1883.
3.	Ρύθμιση για αποδοχή εξωτερικών συνδέσεων: Από προεπιλογή, το Mosquitto ίσως δεν δέχεται συνδέσεις από το Docker. Επεξεργαστείτε το αρχείο ρυθμίσεων:
sudo nano /etc/mosquitto/conf.d/default.conf

Προσθέστε τις εξής δύο γραμμές και αποθηκεύστε (Ctrl+O, Enter, Ctrl+X):
listener 1883
allow_anonymous true

4.	Κάντε επανεκκίνηση την υπηρεσία:
sudo systemctl restart mosquitto
sudo systemctl enable mosquitto

Βήμα 3: Εγκατάσταση Docker
1.	Ελέγξτε αν υπάρχει ήδη το Docker:
docker --version
docker compose version

Αν σας επιστρέψει "command not found", προχωρήστε στην εγκατάσταση.
2.	Κατεβάστε και τρέξτε το επίσημο script εγκατάστασης (χρειάζεται 1-2 λεπτά):
curl -fsSL [https://get.docker.com](https://get.docker.com) | sh

3.	Δώστε δικαιώματα στον χρήστη σας: Για να μην χρειάζεται να γράφετε sudo πριν από κάθε εντολή Docker, προσθέστε τον χρήστη σας στο group του docker:
sudo usermod -aG docker $USER
⚠️ Προσοχή: Αφού τρέξετε την παραπάνω εντολή, γράψτε exit για να βγείτε από το SSH και συνδεθείτε ξανά, ώστε να εφαρμοστούν τα νέα δικαιώματα.
Βήμα 4: Εγκατάσταση Home Assistant
1.	Δημιουργήστε έναν φάκελο για τα αρχεία ρυθμίσεων του Home Assistant:
mkdir -p ~/homeassistant/config

2.	Κατεβάστε και τρέξτε το Home Assistant container:
docker run -d \
  --name homeassistant \
  --restart unless-stopped \
  -v ~/homeassistant/config:/config \
  -v /run/dbus:/run/dbus:ro \
  --network host \
  ghcr.io/home-assistant/home-assistant:stable

3.	Ανοίξτε έναν browser στον υπολογιστή σας και πηγαίνετε στη διεύθυνση:
http://<pi-ip>:8123 (αντικαταστήστε το <pi-ip> με την IP του Pi σας).
4.	Ακολουθήστε τις οδηγίες στην οθόνη για να δημιουργήσετε τον (τοπικό) λογαριασμό σας (όνομα, username, password) και ορίστε την τοποθεσία σας. Παραλείψτε προς το παρόν την εύρεση έξυπνων συσκευών και προχωρήστε στο κεντρικό Dashboard.
Βήμα 5: Σύνδεση Home Assistant με MQTT
Μέσα από το γραφικό περιβάλλον (UI) του Home Assistant:
1.	Πηγαίνετε: Settings (Ρυθμίσεις) -> Devices & Services (Συσκευές & Υπηρεσίες).
2.	Πατήστε Add Integration (Προσθήκη Ολοκλήρωσης) (το κουμπί κάτω δεξιά).
3.	Αναζητήστε τη λέξη MQTT και επιλέξτε το.
4.	Στις ρυθμίσεις του Broker συμπληρώστε:
○	Broker: localhost (ή την IP του Raspberry Pi)
○	Port: 1883
○	Αφήστε τα πεδία Username και Password κενά.
5.	Πατήστε Submit (Υποβολή).
Βήμα 6: Εκκίνηση της Εφαρμογής SmartBin
Τώρα που όλα τα υποσυστήματα τρέχουν, μπορούμε να εκκινήσουμε το δικό μας πρόγραμμα, το οποίο θα στείλει τα δεδομένα και θα δημιουργήσει αυτόματα τα Entities στο Home Assistant.
1.	Στο τερματικό του Raspberry Pi, μεταβείτε στον φάκελο main του project:
cd ~/SmartBin/main

2.	Σηκώστε τα containers της εφαρμογής με το Docker Compose:
docker compose up --build -d

Βήμα 7: Εγκατάσταση HACS στο Home Assistant
Το HACS (Home Assistant Community Store) είναι απαραίτητο για να εγκαταστήσουμε custom κάρτες εμφάνισης για το Dashboard.
1.	Βρείτε το ακριβές όνομα του Home Assistant container (λογικά είναι homeassistant):
docker ps

2.	Εισέλθετε στο "μυαλό" του container:
docker exec -it homeassistant bash

3.	Τρέξτε το script εγκατάστασης του HACS:
wget -O - [https://get.hacs.xyz](https://get.hacs.xyz) | bash -

Μόλις δείτε το μήνυμα "Installation complete", γράψτε exit για να επιστρέψετε στο κανονικό τερματικό.
4.	Κάντε επανεκκίνηση το Home Assistant:
docker restart homeassistant

5.	Επιστρέψτε στο UI του Home Assistant: Πηγαίνετε Settings -> Devices & Services -> Add Integration, αναζητήστε HACS, τσεκάρετε τα 4 κουτάκια και ακολουθήστε τις οδηγίες εξουσιοδότησης με τον λογαριασμό σας στο GitHub.
Βήμα 8: Προσθήκη Custom Καρτών (Frontend)
Από το αριστερό μενού στο Home Assistant, επιλέξτε το HACS και μετά Frontend. Πρέπει να αναζητήσετε και να κατεβάσετε (Download) τις εξής κάρτες:
●	Mushroom: Για όμορφα κουμπιά και ενδείξεις.
●	layout-card: Για τον διαχωρισμό του layout σε στήλες (grid).
●	card-mod: Για την παραμετροποίηση του CSS (π.χ. scrollbars).
●	auto-entities: Για αυτόματη εμφάνιση κάδων ανάλογα με τα φίλτρα.
●	decluttering-card: Για επαναχρησιμοποίηση κώδικα (templates).
●	config-template-card: Για δυναμικό πέρασμα μεταβλητών.
●	ApexCharts Card: Για τα γραφήματα και το ιστορικό.
⚠️ Ειδική οδηγία για τη Bar Card (Μπάρα Χωρητικότητας):
1.	Μέσα στο HACS -> Frontend, πατήστε τις 3 κάθετες τελείες πάνω δεξιά.
2.	Επιλέξτε Custom repositories (Προσαρμοσμένα αποθετήρια).
3.	Συμπληρώστε:
○	Repository: https://github.com/custom-cards/bar-card
○	Category: Dashboard (ή Lovelace)
4.	Πατήστε Add (Προσθήκη). Στη συνέχεια κατεβάστε την κανονικά.
(Μετά την εγκατάσταση των καρτών, το σύστημα ίσως σας ζητήσει να κάνετε Reload τον browser).
Βήμα 9: Δημιουργία του Custom Dashboard
1.	Στο Home Assistant UI, πηγαίνετε Settings -> Dashboards -> Add Dashboard.
2.	Επιλέξτε New dashboard from scratch.
3.	Δώστε έναν τίτλο (π.χ. SmartWaste Bins), επιλέξτε ένα εικονίδιο και πατήστε Create.
4.	Ανοίξτε το νέο Dashboard από το αριστερό μενού.
5.	Πάνω δεξιά, πατήστε το εικονίδιο με το μολύβι (Edit dashboard).
6.	Πατήστε τις 3 κάθετες τελείες πάνω δεξιά και επιλέξτε Raw configuration editor.
7.	Σβήστε ό,τι κώδικα υπάρχει εκεί από προεπιλογή.
8.	Ανοίξτε το αρχείο homeassistant/main_dashboard.yaml από τον κώδικα που κατεβάσατε, αντιγράψτε όλο το περιεχόμενό του και κάντε επικόλληση (Paste) στον editor του Home Assistant.
9.	Πατήστε Save και βγείτε από τη λειτουργία επεξεργασίας.
Βήμα 10: Ρύθμιση Helpers (configuration.yaml)
Για να λειτουργούν σωστά τα φίλτρα και η αλλαγή σελίδων στο dashboard, πρέπει να προσθέσουμε κάποιους "Helpers" (Βοηθητικές μεταβλητές) στο configuration του Home Assistant.
1.	Στο τερματικό του Raspberry Pi, ανοίξτε το αρχείο ρυθμίσεων του HA:
nano ~/homeassistant/config/configuration.yaml

2.	Στο τέλος αυτού του αρχείου, κάντε αντιγραφή/επικόλληση όλο το περιεχόμενο από το δικό μας αρχείο homeassistant/helpers.yaml.
(Προσοχή στις εσοχές / indentation του YAML, αν και η αντιγραφή συνήθως τις διατηρεί σωστά).
Αποθηκεύστε και βγείτε (Ctrl+O, Enter, Ctrl+X).
3.	Για να φορτώσουν οι αλλαγές, κάντε επανεκκίνηση το Home Assistant:
docker restart homeassistant

Τελικός Έλεγχος 🎉
Μεταβείτε στο Dashboard σας. Αν όλα έχουν γίνει σωστά, θα πρέπει να βλέπετε τους κάδους που δημιουργήθηκαν από τον producer και τον χάρτη!
Σημείωση: Αν η λίστα είναι άδεια στην αρχή, ελέγξτε τα φίλτρα (πάνω αριστερά στο dashboard) και βεβαιωθείτε ότι δεν περιορίζουν τα αποτελέσματα.
