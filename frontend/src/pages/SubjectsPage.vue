<template>
  <main class="page">
    <section class="card wide">
      <h1>Detected Study Subjects</h1>
      <p v-if="loading">Loading subjects...</p>
      
      <div v-else>
        <!-- 1. SĄRAŠAS: Rodomas tik jei yra dalykų -->
        <ul v-if="subjects.length" class="subjects-list">
          <li v-for="(subject, index) in subjects" :key="index" class="subject-item">
            <div class="subject-content">
              <div><span class="number">{{ index + 1 }}.</span> {{ subject }}</div>
              <div class="stars" aria-label="Subject rating">
                <button
                  v-for="star in 5"
                  :key="`${subject}-${index}-${star}`"
                  type="button"
                  class="star-button"
                  :class="{ active: star <= (ratings[index] || 0) }"
                  :aria-label="`Rate ${subject}: ${star} star${star > 1 ? 's' : ''}`"
                  @click="setRating(index, star)"
                >
                  ★
                </button>
              </div>
            </div>
            <button @click="removeSubject(index)" class="btn-delete">🗑️</button>
          </li>
        </ul>

        <div v-else class="empty-warning">
          <div class="warning-icon">⚠️</div>
          <div class="warning-text">
            <strong>List is empty! Add subjects below or Go Back to try and detect subjects again.</strong>
          </div>
        </div>

        <div class="add-subject-container">
          <input 
            v-model="newSubjectName" 
            @keyup.enter="addSubject"
            type="text" 
            placeholder="Enter new subject name..." 
            class="input-add"
          />
          <button @click="addSubject" class="btn-add">Add Subject</button>
        </div>

        <div class="button-group">
          <button @click="handleViewEvents" class="btn-events" :disabled="savingBeforeEvents">{{ savingBeforeEvents ? "Saving..." : "View Events" }}</button>
          <button @click="$router.push('/')" class="btn-back">Go Back</button>
        </div>
        <p v-if="saveNotice" :class="saveNoticeType === 'error' ? 'error-message' : 'success-message'">{{ saveNotice }}</p>
      </div>
    </section>
  </main>
</template>

<script>
export default {
  name: "SubjectsPage",
  data() {
    return {
      subjects: [],
      ratings: [],
      originalRatings: [],
      subjectIds: [],
      loading: true,
      savingBeforeEvents: false,
      saveNotice: "",
      saveNoticeType: "success",
      newSubjectName: "",
    };
  },
  methods: {
    removeSubject(index) {
      this.subjects.splice(index, 1);
      this.ratings.splice(index, 1);
      this.subjectIds.splice(index, 1);
    },
    addSubject() {
      const name = this.newSubjectName.trim();
      if (name) {
        this.subjects.push(name);
        this.ratings.push(0);
        this.subjectIds.push(null);
        this.newSubjectName = "";
      }
    },
    async ensureSubjectId(index) {
      const existingId = this.subjectIds[index];
      if (existingId) {
        return existingId;
      }

      const subjectName = (this.subjects[index] || "").trim();
      if (!subjectName) {
        return null;
      }

      const nameKey = subjectName.toLowerCase();

      const studentSubjectsResponse = await fetch("/api/student/1/subjects/");
      const studentSubjectsData = await studentSubjectsResponse.json().catch(() => ({}));
      if (studentSubjectsResponse.ok && Array.isArray(studentSubjectsData.subjects)) {
        const match = studentSubjectsData.subjects.find(
          (item) => String(item.name || "").trim().toLowerCase() === nameKey
        );
        if (match && match.subject_id) {
          this.subjectIds.splice(index, 1, match.subject_id);
          return match.subject_id;
        }
      }

      const createResponse = await fetch("/api/add-subject/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ name: subjectName }),
      });
      const createData = await createResponse.json().catch(() => ({}));

      if (createResponse.ok && createData.subject_id) {
        this.subjectIds.splice(index, 1, createData.subject_id);
        return createData.subject_id;
      }

      if (createResponse.status === 400 && String(createData.error || "").includes("already exists")) {
        const refreshResponse = await fetch("/api/student/1/subjects/");
        const refreshData = await refreshResponse.json().catch(() => ({}));
        if (refreshResponse.ok && Array.isArray(refreshData.subjects)) {
          const match = refreshData.subjects.find(
            (item) => String(item.name || "").trim().toLowerCase() === nameKey
          );
          if (match && match.subject_id) {
            this.subjectIds.splice(index, 1, match.subject_id);
            return match.subject_id;
          }
        }
      }

      return null;
    },
    async saveRating(index) {
      const subjectId = await this.ensureSubjectId(index);
      const interest = this.ratings[index] || 0;

      if (interest < 1) {
        return { ok: true, skipped: true };
      }

      if (interest === (this.originalRatings[index] || 0)) {
        return { ok: true, skipped: true };
      }

      if (!subjectId) {
        throw new Error("Subject id is missing, rating was not saved.");
      }

      const response = await fetch("/api/add-interest/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          subject_id: subjectId,
          interest,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error || "Failed to save rating.");
      }

      return { ok: true, skipped: false };
    },
    async setRating(index, stars) {
      const previous = this.ratings[index] || 0;
      this.ratings.splice(index, 1, stars);

      try {
        const result = await this.saveRating(index);
        if (!result.skipped) {
          this.originalRatings.splice(index, 1, stars);
        }
      } catch (error) {
        this.ratings.splice(index, 1, previous);
        this.saveNoticeType = "error";
        this.saveNotice = error.message || "Failed to save rating.";
      }
    },
    async handleViewEvents() {
      this.savingBeforeEvents = true;
      this.saveNotice = "";

      try {
        const results = await Promise.all(
          this.subjects.map(async (_, index) => {
            try {
              const result = await this.saveRating(index);
              return { ok: result.ok, skipped: Boolean(result.skipped) };
            } catch (error) {
              return { ok: false, error: error.message || "Save failed." };
            }
          })
        );

        const failed = results.filter((item) => !item.ok);
        if (failed.length) {
          this.saveNoticeType = "error";
          this.saveNotice = `Saving ratings failed for ${failed.length} subject(s). Please try again.`;
          return;
        }

        this.saveNoticeType = "success";
        this.saveNotice = "Ratings saved successfully. Opening events...";
        setTimeout(() => this.$router.push('/events'), 1000);
      } finally {
        this.savingBeforeEvents = false;
      }
    }
  },
  async mounted() {
    try {
      const [subjectsResponse, studentSubjectsResponse] = await Promise.all([
        fetch("/api/get-latest-subjects/"),
        fetch("/api/student/1/subjects/"),
      ]);

      const subjectsData = await subjectsResponse.json().catch(() => ({}));
      const studentSubjectsData = await studentSubjectsResponse.json().catch(() => ({}));

      if (Array.isArray(subjectsData.study_subjects)) {
        this.subjects = subjectsData.study_subjects;

        const byName = new Map(
          Array.isArray(studentSubjectsData.subjects)
            ? studentSubjectsData.subjects.map((item) => [item.name, item])
            : []
        );

        this.ratings = this.subjects.map((name) => {
          const row = byName.get(name);
          return row && row.interest ? row.interest : 0;
        });

        this.originalRatings = [...this.ratings];

        this.subjectIds = this.subjects.map((name) => {
          const row = byName.get(name);
          return row ? row.subject_id : null;
        });
      }
    } catch (error) {
      console.error("Error loading subjects:", error);
    } finally {
      this.loading = false;
    }
  },
};
</script>

<style scoped>
/* Visi tavo ankstesni stiliai lieka galioti */
.button-group {
  display: flex;
  gap: 1rem;
  justify-content: center;
  margin-top: 1rem;
}
/* Tavo esami stiliai... */
.page {
  min-height: 100vh;
  display: grid;
  place-items: center;
  background: linear-gradient(135deg, #f3f8ff 0%, #e3f2eb 100%);
  padding: 2rem;
  font-family: "Segoe UI", sans-serif;
}

.card.wide {
  width: min(800px, 100%);
  background: #ffffff;
  border-radius: 12px;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.08);
  padding: 2rem;
}

.subjects-list {
  list-style: none;
  padding: 0;
  margin: 1.5rem 0;
  text-align: left;
}

.subject-item {
  display: flex; /* Pridėta, kad mygtukas būtų šone */
  justify-content: space-between;
  align-items: center;
  padding: 0.75rem;
  background: #f8f9fa;
  border-radius: 8px;
  border-left: 4px solid #1976d2;
  font-size: 0.95rem;
  margin-bottom: 0.5rem;
}

.subject-content {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  flex: 1;
}

.stars {
  display: inline-flex;
  gap: 0.2rem;
}

.star-button {
  border: none;
  background: transparent;
  color: #c8ccd3;
  font-size: 1rem;
  line-height: 1;
  cursor: pointer;
  padding: 0;
}

.star-button.active {
  color: #f5b301;
}

/* Mygtuko stilius */
.btn-delete {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 1.2rem;
  padding: 0.2rem 0.5rem;
  border-radius: 4px;
  transition: background 0.2s;
}

.btn-delete:hover {
  background: #ffebee;
}

.number {
  font-weight: bold;
  color: #1976d2;
  margin-right: 5px;
}

.btn-back {
  margin-top: 1rem;
  padding: 0.65rem 1.5rem;
  border: 1px solid #1976d2;
  background: transparent;
  color: #1976d2;
  border-radius: 8px;
  cursor: pointer;
  font-weight: 600;
}

.btn-back:hover {
  background: #e3f2fd;
}

.btn-events {
  margin-top: 1rem;
  padding: 0.65rem 1.5rem;
  border: none;
  background: #1976d2;
  color: #ffffff;
  border-radius: 8px;
  cursor: pointer;
  font-weight: 600;
}

.btn-events:hover {
  background: #115aa0;
}

.error-message {
  color: #d32f2f;
  font-weight: 600;
}

.success-message {
  color: #1b5e20;
  font-weight: 600;
  margin-top: 0.75rem;
}

.add-subject-container {
  display: flex;
  gap: 0.5rem;
  margin: 1.5rem 0;
  padding: 1rem;
  background: #f1f5f9;
  border-radius: 10px;
}

.input-add {
  flex: 1;
  padding: 0.65rem 0.75rem;
  border: 1px solid #bfcad8;
  border-radius: 8px;
  font-size: 1rem;
}

.btn-add {
  padding: 0.65rem 1.2rem;
  background: #1b5e20; /* Žalia spalva pridėjimui */
  color: white;
  border: none;
  border-radius: 8px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s;
}

.btn-add:hover {
  background: #144316;
}
</style>