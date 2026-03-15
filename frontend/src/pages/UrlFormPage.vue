<template>
  <main class="page">
    <section class="card">
      <h1>Submit a URL</h1>
      <p>Enter a valid URL of your university programme page and click submit.</p>

      <form @submit.prevent="handleSubmit" class="url-form">
        <div class="field">
          <label for="urlInput">URL</label>
          <input
            id="urlInput"
            v-model.trim="url"
            type="url"
            placeholder="https://vilniustech.lt/stojantiesiems/studiju-programos/..."
            required
          />
        </div>

        <!-- SEMESTRŲ DALIS: Sucentruota -->
        <div class="semester-container">
          <div class="semester-row">
            <div class="field">
              <label for="fromSem">Nuo semestro</label>
              <input
                id="fromSem"
                v-model.number="fromSemester"
                type="number"
                min="1"
                max="8"
                required
              />
            </div>
            <div class="field">
              <label for="toSem">Iki semestro</label>
              <input
                id="toSem"
                v-model.number="toSemester"
                type="number"
                min="1"
                max="8"
                required
              />
            </div>
          </div>
          
          <!-- KLAIDOS PRANEŠIMAS -->
          <p v-if="fromSemester > toSemester" class="error-message">
            ⚠️ Pradžios semestras negali būti didesnis už pabaigos.
          </p>
        </div>

        <div class="button-wrapper">
          <button type="submit" :disabled="fromSemester > toSemester || loading">
            {{ loading ? "Submitting..." : "Submit" }}
          </button>
        </div>
      </form>

      <p v-if="submittedInfo" class="result">
        Submitted: {{ submittedInfo.url }} <br>
        <small>(Semesters: {{ submittedInfo.from }} - {{ submittedInfo.to }})</small>
        <br>
        <small v-if="submittedInfo.file">Saved to: {{ submittedInfo.file }}</small>
      </p>

      <p v-if="errorMessage" class="error-message">{{ errorMessage }}</p>
    </section>
  </main>
</template>

<script>
export default {
  name: "UrlFormPage",
  data() {
    return {
      url: "",
      fromSemester: 1,
      toSemester: 1,
      submittedInfo: null,
      loading: false,
      errorMessage: "",
    };
  },
  methods: {
    async handleSubmit() {
      if (this.fromSemester <= this.toSemester) {
        this.errorMessage = "";
        this.loading = true;

        try {
          const response = await fetch("/api/scrape-text/", {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify({
              url: this.url,
              fromSemester: this.fromSemester,
              toSemester: this.toSemester,
            }),
          });

          const data = await response.json();
          if (!response.ok) {
            throw new Error(data.error || "Request failed");
          }

          this.$router.push("/subjects");
          
          this.submittedInfo = {
            url: this.url,
            from: this.fromSemester,
            to: this.toSemester,
            file: data.file,
          };
        } catch (error) {
          this.errorMessage = error.message || "Failed to submit URL.";
        } finally {
          this.loading = false;
        }
      }
    },
  },
};
</script>

<style scoped>
/* TAVO ESAMI STILIAI (NEKEISTI) */
.page {
  min-height: 100vh;
  display: grid;
  place-items: center;
  background: linear-gradient(135deg, #f3f8ff 0%, #e3f2eb 100%);
  padding: 1rem;
  font-family: "Segoe UI", Tahoma, Geneva, Verdana, sans-serif;
}

.card {
  width: min(560px, 100%);
  background: #ffffff;
  border-radius: 12px;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.08);
  padding: 1.5rem;
  text-align: center; /* Pridėta tekstui sucentruoti */
}

h1 { margin: 0 0 0.5rem; }
p { margin: 0 0 1rem; color: #4a5565; }

.url-form {
  display: grid;
  gap: 1.25rem;
  text-align: left; /* Užtikrina, kad etiketės liktų kairėje virš inputų */
}

label { font-weight: 600; display: block; margin-bottom: 0.35rem; }

input {
  padding: 0.65rem 0.75rem;
  border: 1px solid #bfcad8;
  border-radius: 8px;
  font-size: 1rem;
  width: 100%;
}

input:focus {
  outline: 2px solid #1976d2;
  border-color: transparent;
}

/* SUCENTRAVIMO PATOBULINIMAI */
.semester-container {
  display: grid;
  gap: 0.5rem;
}

.semester-row {
  display: flex;
  gap: 1.5rem;
  justify-content: space-between;
}

.button-wrapper {
  display: flex;
  justify-content: center; /* Sucentruoja Submit mygtuką */
}

button {
  padding: 0.75rem 2rem;
  border: none;
  border-radius: 8px;
  background: #1976d2;
  color: #fff;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.2s;
}

button:hover:not(:disabled) {
  background: #115aa0;
}

button:disabled {
  background: #bfcad8;
  cursor: not-allowed;
  opacity: 0.7;
}

/* KLAIDOS STILIUS */
.error-message {
  color: #d32f2f;
  font-size: 0.85rem;
  font-weight: 600;
  margin: 0;
  text-align: center;
}

.result {
  margin-top: 1.5rem;
  font-weight: 600;
  color: #1b5e20;
  word-break: break-all;
}

.field {
  flex: 1;
}
</style>