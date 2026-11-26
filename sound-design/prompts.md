# Саунд-дизайн промптары (референстен көшірілген)

Бұл промпттар референс видеодағы дыбыстардың сипаттамасы. Оларды AI дыбыс генераторларына қоюға болады
(ElevenLabs Sound Effects, Stable Audio, Suno/Udio — музыка үшін) немесе Freesound/Envato-дан іздеу
сұранысы ретінде қолдануға болады. Промпттар ағылшынша жазылған, себебі бұл генераторлар ағылшын тілін
жақсы түсінеді.

Осы жобада әр дыбыс `tools/sfx_synth.py` скриптімен **нөлден синтезделді**, сондықтан авторлық құқық
мәселесі жоқ. Дайын файлдар `sfx/` папкасында.

## SFX промптары

| # | Атауы (`sfx/`) | Қашан қолданылады | Промпт (ағылшынша) |
|---|---|---|---|
| 1 | `whoosh` | Кәдімгі ауысу, зум қозғалысы | `Fast cinematic whoosh transition, airy swoosh passing left to right, clean, no reverb tail, 0.4 seconds` |
| 2 | `whip` | Жылдам punch зум-ин | `Very short whip swish, high-pitched air cut, snappy and dry, 0.2 seconds, for a quick zoom punch-in` |
| 3 | `whoosh_long` | Тегіс зум-аут | `Smooth wide whoosh sweeping across the stereo field, medium length, soft air, 0.65 seconds` |
| 4 | `whoosh_down` | Зум-аут, кадр карточкаға кішірейгенде | `Descending whoosh, pitch falling from high to low, zoom-out transition, soft low air movement, 0.55 seconds` |
| 5 | `whoosh_up` | Зум-ин, кадр қайта толық экранға шыққанда | `Rising whoosh, pitch going up, quick zoom-in transition, airy and bright, 0.5 seconds` |
| 6 | `reverse_whoosh` | Impact алдындағы «сору» | `Reverse whoosh sucking into an impact, builds fast and stops abruptly, 0.5 seconds` |
| 7 | `whoosh_blur` | Blur / фокус ауысуы | `Muffled deep whoosh with a low sub swell, dreamy defocus transition, 0.7 seconds` |
| 8 | `whoosh_out` / `whoosh_out_soft` | Интро reveal, финалдағы зум-аут | `Airy whoosh fading out, starts bright and dissolves into soft wind, 0.5 seconds` |
| 9 | `click` | Мәтін немесе бейдж шыққанда, кесу кезінде | `Crisp minimal UI click, iPhone-style tap, clean and dry, 50 milliseconds` |
| 10 | `pop` | Мәтін, иконка немесе карточка шыққанда | `Cute bubble pop for text appearing on screen, short, dry, slightly pitched down, 0.1 seconds` |
| 11 | `impact_boom` | Хук (0 с) және негізгі ой | `Deep cinematic boom impact with sub-bass drop, punchy transient, short dark reverb tail, 2 seconds` |
| 12 | `hit` | Маңызды сөзге екпін (қызыл мәтін slam) | `Punchy trailer hit, tight low end with a snappy noisy top, 0.8 seconds` |
| 13 | `thump` | Blur-дан кейін жұмсақ түсу | `Soft low thump like a muted kick drum, subtle, 0.4 seconds` |
| 14 | `riser` | Прогресс жүргенде немесе шиеленіс | `Short tension riser, white-noise sweep up with a rising synth tone and accelerating tremolo, ends abruptly, 1.3 seconds` |
| 15 | `shimmer` | Жарық жарқылы (flash / light leak) | `Magical sparkle shimmer, glittery high chimes with an airy swoosh, light-leak flash, 0.8 seconds` |
| 16 | `ding` | «Дайын / 100%», финал | `Bright success notification ding, two-tone bell chime going up, positive and clean, 1.5 seconds` |
| 17 | `shutter` | Кең кадрға зум-аут | `DSLR camera shutter click, mechanical, dry, 0.2 seconds` |
| 18 | *(референсте)* typing | Чатқа жазғанда | `Soft iPhone keyboard typing, 8 quick taps, dry, close-mic, 1.2 seconds` |
| 19 | *(референсте)* send | Жіберу батырмасы | `Message sent sound, short upward swoosh ending in a soft pop, 0.3 seconds` |
| 20 | *(референсте)* counter | Сандар өскенде | `Fast digital counter ticking, tiny UI ticks accelerating, 0.6 seconds` |

## Музыка промпты (Suno / Udio, вокалсыз)

```
Upbeat modern lo-fi trap pop instrumental, 95 BPM, C major, warm pad chords C–G–Am–F,
punchy 808 bass, crisp hi-hats with 16th rolls, claps on 2 and 4, bright plucked arpeggio
with dotted-eighth delay, side-chain pumping, positive and confident mood, no vocals,
starts immediately with no intro, made as a background bed for an Instagram Reels voice-over
```

Бұл жобадағы музыка (`tools/music_synth.py`) осы сипаттамамен синтезделді. Аранжировкасы:

- 0 с-та crash соғылады, музыка бірден толық күйінде басталады.
- 11,50–12,00 с аралығында барабандар өшеді (drum break), reverse cymbal ойнайды. Бұл зум-аут/карточка
  ауысуымен сәйкес келеді. 12,00 с-та crash соғылып, барабан қайта кіреді.
- 18,80 с-та барабандар тоқтайды, тек аккорд қалады. 18,90–19,72 с аралығында музыка біртіндеп өшеді.

## Микс деңгейлері

| Шина | Деңгейі |
|---|---|
| Дауыс | −16 LUFS. Өңдеу: HPF 85 Гц, шуды жеңіл азайту, 220 Гц −2 дБ, 3,2 кГц +3 дБ, 9 кГц shelf +2 дБ, компрессор 3:1 |
| Музыка | Сөйлеп тұрғанда дауыстан −17 дБ, паузада −11 дБ (ducking). Сөйлеп тұрғанда 1–4 кГц жолағы дауысқа орын беру үшін басылады |
| SFX | −6 дБ шина, әр дыбыстың өз gain-і бар (`edit_plan.json`) |
| Мастер | −14 LUFS, true peak −1 dBTP (Instagram/TikTok стандарты) |
