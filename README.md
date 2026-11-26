# Reels-creative-

Сөйлеп тұрған адамның (talking-head) видеосына Reels стиліндегі монтажды автоматты түрде жасайтын құрал.
Ол бетке бағытталған зум-ин/зум-аут, whoosh/click/pop/impact SFX, авторлық құқықсыз музыка, ducking және
−14 LUFS мастеринг қосады. Барлық дыбыс пен музыка кодпен синтезделеді, сондықтан лицензия мәселесі жоқ.

## Жобалар

| Жоба | Нәтиже | Референс |
|---|---|---|
| `projects/dentist-reel` | `output/dentist_reel_final.mp4` (1080×1920, 30 fps, 19,7 с) | https://www.instagram.com/reel/DfwNBVvN-WQ/ |

## Құрылымы

```
projects/<name>/edit_plan.json   монтаж жоспары: сөйлеу фразалары, зум кадрлары, fx, SFX уақыттары, музыка
sound-design/reference_analysis.md   референстің әр 0,5 с сайынғы талдауы
sound-design/prompts.md          SFX және музыка промптары (ElevenLabs / Suno үшін), микс деңгейлері
sfx/                             синтезделген SFX кітапханасы + index.json (әр дыбыстың "hit" нүктесі)
tools/sfx_synth.py               SFX синтезі
tools/music_synth.py             музыка синтезі (95 BPM, C–G–Am–F, 808, sidechain)
tools/render_video.py            бетті бақылайтын зум, motion blur, flash, blur, «карточка» зум-аут
tools/mix_audio.py               дауыс өңдеу, ducking, SFX орналастыру, −14 LUFS мастер
tools/build.sh                   бүкіл pipeline-ды іске қосады
```

## Қайта жинау

Талап етілетіндер: `ffmpeg`, Python 3, `numpy`, `scipy`, `opencv-python-headless<5`.

```bash
pip install numpy scipy "opencv-python-headless<5"
```

```bash
tools/build.sh SOURCE.mp4 projects/dentist-reel/edit_plan.json output/dentist_reel_final.mp4
```

Зум, SFX немесе музыканы өзгерту үшін `edit_plan.json` файлын түзетіп, скриптті қайта іске қосыңыз.

- `zoom`: `[уақыт, зум, ease]`. `1.0` толық кадр, `>1` бетке жақындау, `<1` ашық сұр фондағы «карточка».
  Ease мәндері: `hold`, `linear`, `ease`, `expo`, `punch`.
- `sfx`: `[уақыт, дыбыс, gain]`. Уақыт дыбыстың ең күшті нүктесі (hit) түсетін сәт.
