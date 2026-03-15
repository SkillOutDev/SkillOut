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
              <span class="number">{{ index + 1 }}.</span> {{ subject }}
            </div>
            <button @click="removeSubject(index)" class="btn-delete">🗑️</button>
          </li>
        </ul>

        <div v-else class="empty-warning">
          <div class="warning-icon">⚠️</div>
          <div class="warning-text">
            <strong>Sąrašas tuščias!</strong>
            <p>Be studijų dalykų renginių paieška negalima. Prašome pridėti bent vieną dalyką žemiau arba pradėti scrapinimą iš naujo.</p>
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
          <button @click="$router.push('/')" class="btn-back">Go Back</button>
        </div>
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
      loading: true,
      newSubjectName: "",
    };
  },
  methods: {
    removeSubject(index) {
      this.subjects.splice(index, 1);
    },
    addSubject() {
      const name = this.newSubjectName.trim();
      if (name) {
        this.subjects.push(name);
        this.newSubjectName = "";
      }
    }
  },
  async mounted() {
    try {
      const response = await fetch("/api/get-latest-subjects/");
      const data = await response.json();
      if (data.study_subjects) {
        this.subjects = data.study_subjects;
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

.error-message {
  color: #d32f2f;
  font-weight: 600;
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