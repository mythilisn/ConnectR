<div align="center">

# connectR

**A smart academic note-sharing and quiz-generation platform built with Django**

![Django](https://img.shields.io/badge/Django-5.2.6-green.svg)
![Python](https://img.shields.io/badge/Python-3.x-blue.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

</div>

---

## Overview

connectR lets students upload, discover, and manage academic notes across semesters and subjects. Its standout feature is AI-powered question generation from uploaded PDFs — turning study material directly into quizzes.
<img width="1689" height="867" alt="image" src="https://github.com/user-attachments/assets/442814a9-d9b9-4474-9439-0ad17a2a78a0" />
<img width="1886" height="854" alt="image" src="https://github.com/user-attachments/assets/1cc0b143-6ad3-4ba5-8b02-2bb2b762aded" />
<img width="1888" height="861" alt="image" src="https://github.com/user-attachments/assets/60737c3b-2bff-4f2d-9ded-3c2360bbbdef" />


## Features

- Secure user authentication & profile management
- Upload notes in PDF, DOCX, PPTX, and TXT formats
- Browse/filter notes by semester, subject, tag, or uploader
- Keyword and natural-language search
- AI-powered note summarization & auto-tagging
- PDF-based question generation and quiz-taking
- Ratings, feedback, and reporting system

## Tech Stack

**Backend:** Python, Django, SQLite
**Frontend:** HTML, CSS, Bootstrap, Django Templates
**AI/Parsing:** OpenAI / Gemini API, PyPDF2, python-pptx, docx2txt, pytesseract, Pillow

## Getting Started

```bash
git clone <your-repository-url>
cd connectR
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # macOS/Linux

pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Visit `http://127.0.0.1:8000/`, register an account, and start uploading notes.

## Environment Variables

```env
OPENAI_API_KEY=your_openai_key
GEMINI_API_KEY=your_gemini_key
```

## Roadmap

- [ ] Improve quiz generation quality
- [ ] Add more question types
- [ ] Student performance analytics
- [ ] Support more document formats

## Contributing

Contributions are welcome — fork the repo and submit a pull request.

## License

MIT
