# Smart File Organizer AI

AI-assisted file classification and automatic organization.

## Run

```bash
pip install -r requirements.txt
streamlit run app.py
```

Gemini API key is optional. Without it, the app uses deterministic extension-based classification.

## Demo flow

1. Create a folder containing mixed sample files.
2. Enter that folder in the app.
3. Click Analyze Files.
4. Review the AI classification.
5. Click Organize Files.
6. Show the generated Organized/ folders.
7. Demonstrate Undo Last Organization.

## Safety

The app never moves files during analysis. Movement happens only after the user clicks Organize Files.
