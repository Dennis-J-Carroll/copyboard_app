## Project: DNN-Based Prompt Enhancement App

**Goal:** Develop an application that enhances user prompts using a dedicated Deep Neural Network (DNN), specifically a fine-tuned Sequence-to-Sequence model, rather than relying solely on general-purpose LLMs.

**Core Idea:** Train a model to learn specific patterns of prompt improvement based on a curated dataset of (original prompt, enhanced prompt) pairs.

### Planned Workflow

1.  **Task Definition:**
    *   Clearly define what constitutes an "enhanced" prompt (e.g., adding specificity, context, reformatting for a target model).
    *   **Status:** *Pending User Input* (Need example original vs. enhanced prompt).
2.  **Data Collection/Creation:**
    *   Determine the source for `(original_prompt, enhanced_prompt)` pairs.
    *   Options: Manual creation, synthetic generation (using large LLM API), mining logs.
    *   **Status:** *Pending Decision.*
3.  **Model Selection & Architecture:**
    *   Choose a pre-trained Seq2Seq model (e.g., T5, BART) for fine-tuning.
    *   Initial Choice: `t5-small` (can be changed).
    *   **Status:** *Tentatively Selected.*
4.  **Implementation (`start.py`):**
    *   Set up data loading and preprocessing pipeline (tokenization, etc.).
    *   Integrate model loading from Hugging Face `transformers`.
    *   Implement training loop using `Seq2SeqTrainer`.
    *   Implement evaluation logic (e.g., using ROUGE scores).
    *   Create an inference function `enhance_prompt`.
    *   **Status:** *Initial structure created with placeholders.*
5.  **Training:**
    *   Fine-tune the selected model on the prepared dataset.
    *   Requires setting up environment (`pip install ...`).
    *   **Status:** *Not Started.*
6.  **Evaluation:**
    *   Measure performance on a held-out test set.
    *   Analyze results and identify areas for improvement.
    *   **Status:** *Not Started.*
7.  **Deployment/Integration:**
    *   (Optional) Wrap the inference function in an API (e.g., Flask).
    *   Integrate into the target application (`copyboard_extension`).
    *   **Status:** *Not Started.*

### Next Steps

*   User to provide an example of an original prompt and its desired enhanced version.
*   Decide on the data collection strategy.
*   Begin implementing the `TODO` sections in `start.py`.
*   Install necessary dependencies.

### Change Log

*   **[Timestamp]**: Initial project setup. Created `start.py` with structural placeholders and comments. Created `README.md` outlining goals and plan. (Initiated by Cascade AI)
