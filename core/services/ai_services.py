# core/services/ai_services.py

import os
import json
import time # Added for exponential backoff retry logic
from google import genai
# IMPORTANT: Removed NotFound import to fix the ImportError. 
from google.genai.errors import APIError 
from google.genai import types 
from django.conf import settings
from django.core.cache import cache
from pathlib import Path
from ..models import Note
from pdfminer.high_level import extract_text 


# Initialize the Gemini Client ONCE globally
try:
    api_key = getattr(settings, "GEMINI_API_KEY", None) or os.getenv("GEMINI_API_KEY")
    if api_key:
        client = genai.Client(api_key=api_key)
    else:
        client = None
except Exception as e:
    client = None
    print(f"Gemini client initialization skipped: {e}")


class AIService:
    """Handles all Gemini API calls and AI logic."""
    
    # Model configuration
    CHAT_MODEL = "gemini-2.5-flash"  # Fast for chat
    EXAM_MODEL = "gemini-2.5-pro"    # Better for complex reasoning/structured output
    
    # Keys for cache
    CHAT_CACHE_KEY = "chat_history_{}" 
    FILE_HANDLE_KEY = "gemini_file_handle_{}" 
    FILE_PATH_VERIFY_KEY = "gemini_file_path_check_{}" 


    def __init__(self, note_id, pdf_path):
        self.note_id = note_id
        # Ensure the PDF path is a standard Path object for the API
        self.pdf_path = Path(pdf_path) 
        self.chat_cache_key = self.CHAT_CACHE_KEY.format(note_id)
        self.file_handle_key = self.FILE_HANDLE_KEY.format(note_id)
        self.file_path_verify_key = self.FILE_PATH_VERIFY_KEY.format(note_id)

    # --- File Management (CRITICAL FOR CORRECT CONTEXT) ---

    def _get_or_upload_file(self):
        """Uploads the PDF to Gemini File API or retrieves the existing file reference."""
        file_name = cache.get(self.file_handle_key)
        cached_file_path = cache.get(self.file_path_verify_key)
        current_file_path = str(self.pdf_path)
        
        # ----------------------------------------------------------------------
        # VERIFICATION STEP: 
        # Check 1: Do we have a cached file handle?
        # Check 2: Does the path we used for upload match the path we have now?
        # ----------------------------------------------------------------------
        if file_name and cached_file_path == current_file_path:
            try:
                uploaded_file = client.files.get(name=file_name)
                # Check file status again even if cached
                if uploaded_file.state.name != 'ACTIVE':
                    print(f"Cached file {file_name} not yet ACTIVE. Polling for status...")
                    return self._poll_for_active_status(file_name)
                
                print(f"Using cached Gemini file handle: {file_name}")
                return uploaded_file
            # MODIFIED: Catch APIError and check if it's a NotFound equivalent
            except APIError as e:
                # APIError typically has the status code or message indicating Not Found (404)
                if 'not found' in str(e).lower() or '404' in str(e):
                    print("Cached file handle not found on Gemini API (APIError 404). Forcing re-upload.")
                    file_name = None 
                    cache.delete(self.file_path_verify_key)
                else:
                    print(f"Error retrieving Gemini file handle {file_name}: {e}")
                    file_name = None
                    cache.delete(self.file_path_verify_key)
            except Exception as e:
                print(f"General Error retrieving Gemini file handle {file_name}: {e}")
                file_name = None
                cache.delete(self.file_path_verify_key)

        # ----------------------------------------------------------------------
        # Upload/Re-upload logic (MODIFIED to increase retries to 5)
        # ----------------------------------------------------------------------
        if not file_name or cached_file_path != current_file_path:
            # If we are re-uploading, delete the old file if possible
            if file_name:
                print(f"File path mismatch detected. Deleting old Gemini file {file_name} before re-upload.")
                # We call delete_gemini_file with overrides to prevent infinite recursion
                self.delete_gemini_file(file_name_override=file_name, clear_cache=False)
            
            print(f"Uploading new file for note {self.note_id} from path: {current_file_path}...")
            
            # INCREASED MAX_RETRIES and tuned backoff delay for resiliency
            MAX_RETRIES = 7
            DELAY_SECONDS = 2
            
            for attempt in range(MAX_RETRIES):
                try:
                    # FIX APPLIED: 'mime_type' and 'display_name' removed to resolve 'unexpected keyword argument' errors.
                    uploaded_file = client.files.upload(
                        file=current_file_path
                    )
                    
                    # SUCCESS! Now poll until the file status is ACTIVE (new fix)
                    uploaded_file = self._poll_for_active_status(uploaded_file.name)

                    # Store the new file name (handle) and the path used to verify
                    cache.set(self.file_handle_key, uploaded_file.name, timeout=3600)
                    cache.set(self.file_path_verify_key, current_file_path, timeout=3600)
                    
                    return uploaded_file
                
                except APIError as e:
                    # Check if it's a transient server error (5xx or 429)
                    error_message = str(e)
                    is_transient = '503' in error_message or '500' in error_message or '429' in error_message
                    
                    if is_transient and attempt < MAX_RETRIES - 1:
                        print(f"Transient API Error (Attempt {attempt+1}/{MAX_RETRIES}): {error_message}. Retrying in {DELAY_SECONDS}s...")
                        time.sleep(DELAY_SECONDS)
                        DELAY_SECONDS *= 2 # Exponential backoff
                        continue
                    else:
                        print(f"FATAL: Failed to upload file to Gemini API after {attempt + 1} attempts: {e}")
                        # Re-raise with the descriptive error that the user sees in the frontend
                        raise ValueError("The AI service could not upload the document for analysis.") 
                        
                except Exception as e:
                    # Handle other transient errors from the SDK upload flow
                    err_str = str(e)
                    transient_markers = [
                        'Upload status is not finalized',
                        'Service Unavailable',
                        'temporarily unavailable',
                        'deadline exceeded',
                        'connection reset',
                    ]
                    is_transient_other = any(marker.lower() in err_str.lower() for marker in transient_markers)
                    if is_transient_other and attempt < MAX_RETRIES - 1:
                        print(f"Transient Upload Error (Attempt {attempt+1}/{MAX_RETRIES}): {e}. Retrying in {DELAY_SECONDS}s...")
                        time.sleep(DELAY_SECONDS)
                        DELAY_SECONDS *= 2
                        continue
                    print(f"FATAL: Failed to upload file to Gemini API: {e}")
                    # Non-transient or max retries exhausted
                    raise ValueError("The AI service could not upload the document for analysis.") 

            # This line should technically be unreachable if the loop succeeds or raises a specific error
            raise ValueError("The AI service could not upload the document for analysis after multiple retries.")
            
    def _poll_for_active_status(self, file_name, timeout=120, interval=4):
        """
        Polls the Gemini File API until the file's state is 'ACTIVE' or a timeout occurs.
        This fixes the 'Upload status is not finalized' error.
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                uploaded_file = client.files.get(name=file_name)
                
                if uploaded_file.state.name == 'ACTIVE':
                    print(f"File {file_name} successfully finalized (ACTIVE).")
                    return uploaded_file
                
                elif uploaded_file.state.name == 'FAILED':
                    raise ValueError(f"File processing failed on Gemini API for file {file_name}.")

                # Log status and wait
                print(f"Polling for file status: {uploaded_file.state.name}. Waiting {interval}s...")
                time.sleep(interval)
                
            except APIError as e:
                # If we get an API error during polling, it's likely a temporary issue or the file doesn't exist anymore
                print(f"API Error during status polling for {file_name}: {e}. Retrying.")
                time.sleep(interval)
            except Exception as e:
                # Catch generic exceptions
                print(f"General Error during status polling for {file_name}: {e}. Aborting poll.")
                raise ValueError("An internal error occurred while waiting for document processing.")

        # If the loop finishes without returning, we timed out
        raise ValueError(f"Document processing timed out after {timeout} seconds.")


    def delete_gemini_file(self, file_name_override=None, clear_cache=True):
        """Clean up: Deletes the uploaded file from the Gemini API."""
        file_name = file_name_override or cache.get(self.file_handle_key)
        
        if file_name:
            try:
                client.files.delete(name=file_name)
                print(f"Successfully deleted Gemini file handle: {file_name}")
            except Exception as e:
                print(f"Warning: Failed to delete Gemini file {file_name}: {e}")
            
            if clear_cache:
                cache.delete(self.file_handle_key)
                cache.delete(self.file_path_verify_key)
                cache.delete(self.chat_cache_key)


    # --- Feature 1: AI Chatbot Logic (Context-Aware) ---
    
    def get_initial_history(self, uploaded_file_object):
        """
        Initializes the history with the file reference ONLY (System Instruction 
        is handled separately in send_chat_message).
        NOTE: This history uses simple strings/dictionaries for cache safety.
        """
        
        # Store simple dictionary representation for cache
        # The first part is the file name (URI)
        return [{
            "role": "user", 
            "parts": [
                # Store the actual file URI for the file API
                {"file_uri": getattr(uploaded_file_object, "uri", uploaded_file_object.name)}
            ]
        }]

    def _convert_cache_to_api_contents(self, history):
        """
        Converts the simple cached history (dicts) into the required list of 
        types.Content objects containing types.Part objects, right before the API call.
        """
        api_contents = []
        for history_item in history:
            role = history_item["role"]
            parts = []
            
            for part_data in history_item["parts"]:
                if "text" in part_data:
                    # Use the correct factory method with a keyword argument (safe)
                    parts.append(types.Part.from_text(text=part_data["text"]))
                elif "file_uri" in part_data:
                    # Using the idiomatic types.Part.from_uri() factory method for uploaded files
                    file_uri = part_data["file_uri"]
                    # Backwards compatibility: if we cached a file 'name' like 'files/abc',
                    # resolve it to a proper URI using the Files API.
                    if isinstance(file_uri, str) and file_uri.startswith("files/"):
                        try:
                            file_meta = client.files.get(name=file_uri)
                            if getattr(file_meta, "uri", None):
                                file_uri = file_meta.uri
                        except Exception as e:
                            print(f"Warning: Failed to resolve file handle {file_uri} to URI: {e}")
                    parts.append(types.Part.from_uri(
                        file_uri=file_uri,
                        mime_type="application/pdf"
                    ))
                else:
                    # Safety catch for unknown parts
                    print(f"Warning: Unknown part type found in cache data: {part_data}")
            
            # Use types.Content to ensure proper Pydantic structure for the API call
            api_contents.append(types.Content(role=role, parts=parts))
            
        return api_contents


    def send_chat_message(self, user_message):
        """Sends a message, manages history via cache, and returns the response."""
        
        # 1. Get the file handle (upload if needed)
        try:
            uploaded_file_object = self._get_or_upload_file()
        except ValueError as e:
            # Re-raise the error if upload failed
            raise e

        # 2. Retrieve history. If empty, create new history with the file context.
        history = cache.get(self.chat_cache_key)
        if not history:
            history = self.get_initial_history(uploaded_file_object)
            
        # FIX 4: Define system instruction separately for the API call
        system_instruction_text = (
            "You are a helpful and knowledgeable tutor. Prioritize using the provided PDF as the primary source when relevant, "
            "but you may also draw from your general knowledge to answer questions that are not covered in the PDF. "
            "When an answer goes beyond the PDF, make it clear by saying it is general knowledge. "
            "Provide concise, accurate explanations with step-by-step reasoning only when helpful."
        )


        # 3. Append the new user message (stored as simple text)
        user_message_part_cache = {"text": user_message}

        if len(history) > 1:
            # Standard conversation flow
            history.append({"role": "user", "parts": [user_message_part_cache]})
        else:
            # If it's the very first message, append the user's question to the initial history item.
            # The initial item now only contains the file URI.
            if history and history[0].get("parts"): 
                # Append the simple text part to the first history entry
                history[0]["parts"].append(user_message_part_cache)
            else:
                # Fallback: Treat as a new message if initial structure is unexpected or missing
                history.append({"role": "user", "parts": [user_message_part_cache]})
            
        try:
            # 4. CONVERSION STEP: Convert the cache-safe history to API-ready contents
            api_contents = self._convert_cache_to_api_contents(history)

            # 5. Call the API with the explicit types.Content list
            response = client.models.generate_content(
                model=self.CHAT_MODEL,
                contents=api_contents, # Pass the API-ready contents
                # FIX 4: Pass system instruction as a dedicated parameter
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction_text
                )
            )
            response_text = response.text

            # 6. Append the model response to history and save (stored as simple text)
            model_response_part_cache = {"text": response_text}
            history.append({"role": "model", "parts": [model_response_part_cache]})
            cache.set(self.chat_cache_key, history, timeout=3600) # 1 hour timeout

            return response_text

        except APIError as e:
            print(f"Gemini API Error in chat: {e}")
            # Try to delete the file on API errors to force a clean re-upload next time
            self.delete_gemini_file() 
            raise ValueError("The AI service encountered an API error while generating the response. Please try again.")
        except Exception as e:
            # Catch all generic errors
            print(f"General Error in chat: {e}") 
            # Updated error message to include the generic error content for better debugging
            raise ValueError(f"An unexpected server error occurred during content generation: {e}")

    
    # The get_note_content function is no longer needed for the chat feature 
    # because the File API handles the reading/grounding, but we keep it here 
    # if other parts of your app need raw text content.
    def get_note_content(self, note: Note) -> str:
        """Extracts text content from the uploaded note file."""
        try:
            # WARNING: Placeholder - Adjust 'file' to match your actual model field name (e.g., 'pdf_file')
            file_path = note.file.path 
            file_extension = os.path.splitext(file_path)[1].lower()

            if file_extension == '.pdf':
                return extract_text(file_path)
            
            elif file_extension in ['.txt']:
                with open(file_path, 'r', encoding='utf-8') as f:
                    return f.read()

            return "Error: Unsupported file type for AI analysis."
        
        # Removed extra indentation here
        except Exception as e: 
            print(f"--- FATAL FILE READING ERROR for Note {note.id} at {file_path}: {e} ---")
            return f"Error: File content could not be read due to a processing error. ({e})"


    def get_response(self, note: Note, user_message: str) -> str:
        """Generates an AI response using the note content as context."""
        # For chat persistence, we route this directly to send_chat_message
        return self.send_chat_message(user_message)

    # --- Feature 2: Exam Generator Logic (Placeholder) ---
    # ...
