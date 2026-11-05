# PS2 Karaoke Studio – första PC-versionen

Det här är första byggstenen i projektet. Programmet tar en MP3 och försöker automatiskt skapa:
- `instrumental.wav` – musik utan den separerade sången
- `vocals.wav` – separerad sång som referens
- `lyrics.srt` – text med ungefärliga tidsstämplar
- `lyrics.json` – ord och tidsstämplar
- `pitch.json` – uppskattade tonhöjdssamplingar
- `song.json` – manifest som beskriver låtpaketet

## Windows-installation

1. Installera Python 3.10 eller 3.11 från https://www.python.org/downloads/
2. Ladda ned och packa upp projektet.
3. Dubbelklicka på `STARTA_WINDOWS.bat`.
4. Första installationen kan ta tid och ladda ned stora AI-modeller.
5. Välj en MP3 i programmet och tryck på **Skapa karaokelåt**.
6. När bearbetningen är klar öppnas förhandsgranskningen automatiskt. Där kan du spela/pausa/stoppa, välja instrumental eller sångreferens och följa text/tonhöjd.

En dator med NVIDIA-GPU kan göra Demucs snabbare, men CPU-läge används som standard i den här första versionen. Internet behövs vid installation och första modellhämtningen.

## Viktiga begränsningar

- AI-separation kan lämna kvar sångrester eller ta bort delar av instrumenten.
- Whisper kan höra fel, särskilt vid körsång, effekter eller låg sångvolym.
- `pitch.json` innehåller tonhöjdsprov, inte färdiga SingStar-noter. En senare version behöver slå ihop prover till noter, justera timing och låta användaren redigera resultatet.
- Programmet skapar **inte** en färdig PS2-ISO ännu. PS2-spelet, ljudmotorn, mikrofonläsningen och DVD-byggaren är separata utvecklingssteg.
- PS2 Slim kan inte starta en egenbränd spelskiva på vanligt sätt utan en kompatibel homebrew-startmetod. Kontrollera kompatibilitet och lagliga installationsmetoder för just din konsol innan du bränner skivor.

## Mappstruktur för ett färdigt låtpaket

`PS2_Karaoke_Library/Låtnamn/`
- instrumental.wav
- vocals.wav
- lyrics.srt
- lyrics.json
- pitch.json
- song.json
- NOTES.txt

Använd bara musik och ljudfiler som du har rätt att bearbeta och använda.
