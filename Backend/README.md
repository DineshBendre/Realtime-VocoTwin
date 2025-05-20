# Flask Backend – Realtime-VocoTwin

This is the backend service for Realtime-VocoTwin, built using Python Flask and integrated with Gemini Flash APIs.

---

## 🛠️ Setup Instructions

### 1. Navigate to the Backend directory

```bash
cd Backend
```

### 2. Create and activate a virtual environment

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

### 3. Install required dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure your `.env` file

Create a `.env` file in the `Backend/` folder and add:

```env
GEMINI_API_KEY=your_gemini_api_key
```

### 5. Start the Flask server

```bash
python main.py
```

Server will run at: [http://localhost:5000](http://localhost:5000)

---

## 🔑 Notes

- Ensure `.env` is **not** committed to version control
- Uses `dotenv` to load environment variables
- Compatible with CORS-based frontend requests
