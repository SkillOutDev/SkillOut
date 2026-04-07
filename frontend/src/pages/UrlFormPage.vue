<template>
  <main class="page">
    <section class="card">
      <h1>Enter URL</h1>
      <p>Temporary mode: submit uses cached scraped_text/latest_scrape.txt for AI extraction.</p>

      <form @submit.prevent="handleSubmit" class="url-form">
        <div class="field">
          <label for="urlInput">Enter URL</label>
          <input
            id="urlInput"
            v-model.trim="url"
            type="url"
            placeholder="Optional: original source URL for reference"
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

        <p v-if="loading" class="status-message">
          Reading latest_scrape.txt and extracting subjects. This can take up to ~2 minutes.
        </p>
      </form>

      <p v-if="submittedInfo" class="result">
        Submitted: {{ submittedInfo.url }} <br>
        <small>(Semesters: {{ submittedInfo.from }} - {{ submittedInfo.to }})</small>
        <br>
        <small v-if="submittedInfo.source">Source: {{ submittedInfo.source }}</small>
      </p>

      <section v-if="subjectRows.length" class="subjects-section">
        <h2>Subjects and Ratings</h2>
        <table class="subjects-table">
          <thead>
            <tr>
              <th>Semester</th>
              <th>Subject</th>
              <th>Rating</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in subjectRows" :key="row.id">
              <td>Semester {{ row.semester }}</td>
              <td>{{ row.subject }}</td>
              <td>
                <button
                  v-for="star in 5"
                  :key="`${row.id}-${star}`"
                  type="button"
                  class="star-btn"
                  :class="{ active: (ratings[row.id] || 0) >= star }"
                  @click="setRating(row.id, star)"
                >
                  ★
                </button>
              </td>
            </tr>
          </tbody>
        </table>

        <div v-if="subjectRows.length" class="save-ratings-wrapper">
          <button type="button" class="save-btn" :disabled="savingRatings" @click="saveRatings">
            {{ savingRatings ? "Saving..." : "Submit Ratings" }}
          </button>
          <p v-if="saveMessage" class="save-message">{{ saveMessage }}</p>
          <p v-if="saveError" class="error-message">{{ saveError }}</p>
        </div>
      </section>

      <p v-else-if="submittedInfo" class="result-empty">
        No cached subjects found for selected semesters.
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
      subjectRows: [],
      ratings: {},
      loading: false,
      errorMessage: "",
      savingRatings: false,
      saveMessage: "",
      saveError: "",
    };
  },
  methods: {
    setRating(rowId, stars) {
      this.ratings = {
        ...this.ratings,
        [rowId]: stars,
      };
    },
    async saveRatings() {
      this.savingRatings = true;
      this.saveMessage = "";
      this.saveError = "";
      try {
        const rows = this.subjectRows.map((row) => ({
          semester: row.semester,
          subject: row.subject,
          stars: this.ratings[row.id] || 0,
        }));
        const response = await fetch("/api/save-subject-ratings/", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ rows }),
        });
        const data = await response.json();
        if (!response.ok) {
          this.saveError = data.error || "Failed to save ratings.";
        } else {
          this.saveMessage = `Ratings saved! (${data.count} subject${data.count !== 1 ? 's' : ''})`;
        }
      } catch (err) {
        this.saveError = err.message || "Network error while saving ratings.";
      } finally {
        this.savingRatings = false;
      }
    },
    async handleSubmit() {
      if (this.fromSemester <= this.toSemester) {
        this.errorMessage = "";
        this.loading = true;
        let timeoutId;

        try {
          const controller = new AbortController();
          timeoutId = setTimeout(() => controller.abort(), 5000);

          const response = await fetch("/api/latest-subjects-fast/", {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify({
              url: this.url,
              fromSemester: this.fromSemester,
              toSemester: this.toSemester,
            }),
            signal: controller.signal,
          });

          clearTimeout(timeoutId);

          const rawBody = await response.text();
          let data = {};
          try {
            data = rawBody ? JSON.parse(rawBody) : {};
          } catch {
            if (!response.ok) {
              const snippet = rawBody.slice(0, 120).replace(/\s+/g, " ").trim();
              throw new Error(
                `Server returned non-JSON response (${response.status}). ${snippet || "No response body."}`
              );
            }

            throw new Error("Server returned invalid JSON response.");
          }

          if (!response.ok) {
            throw new Error(data.error || "Request failed");
          }

          this.$router.push("/subjects");
          
          this.submittedInfo = {
            url: data.url || this.url || "latest_scrape.txt",
            from: this.fromSemester,
            to: this.toSemester,
            source: data.source,
          };
          this.subjectRows = Array.isArray(data.rows) ? data.rows : [];
          this.ratings = Object.fromEntries(
            this.subjectRows.map((row) => [row.id, Number.isInteger(row.stars) ? row.stars : 0])
          );
        } catch (error) {
          if (error.name === "AbortError") {
            this.errorMessage = "Cached load timed out. Please try again.";
          } else {
            this.errorMessage = error.message || "Failed to submit URL.";
          }
          this.subjectRows = [];
          this.ratings = {};
        } finally {
          if (timeoutId) {
            clearTimeout(timeoutId);
          }
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
  box-sizing: border-box;
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

.status-message {
  color: #1f2937;
  font-size: 0.9rem;
  margin-top: 0.5rem;
  text-align: center;
}

.subjects-section {
  margin-top: 1rem;
  text-align: left;
}

.subjects-table {
  width: 100%;
  border-collapse: collapse;
  background: #f8fbff;
  border: 1px solid #d7e4f0;
}

.subjects-table th,
.subjects-table td {
  border-bottom: 1px solid #e6edf5;
  padding: 0.55rem;
}

.subjects-table th {
  background: #eef4fb;
}

.star-btn {
  border: none;
  background: transparent;
  color: #c2c8cf;
  font-size: 1.1rem;
  cursor: pointer;
  padding: 0.1rem;
}

.star-btn.active {
  color: #ffb300;
}

.result-empty {
  margin-top: 1rem;
  color: #7a5c00;
  font-weight: 600;
}

.field {
  flex: 1;
  min-width: 0;
}

.save-ratings-wrapper {
  margin-top: 1rem;
  text-align: center;
}

.save-btn {
  padding: 0.65rem 2rem;
  background: #2e7d32;
}

.save-btn:hover:not(:disabled) {
  background: #1b5e20;
}

.save-message {
  color: #2e7d32;
  font-weight: 600;
  margin-top: 0.5rem;
}
</style>
<!-- noop commit marker -->
