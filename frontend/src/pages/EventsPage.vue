<template>
  <main class="page">
    <section class="card">
      <h1>Events</h1>

      <p v-if="loading" class="state">Loading events...</p>
      <p v-else-if="error" class="error-message">{{ error }}</p>
      <p v-else class="state">Total: {{ total }}</p>

      <ul v-if="!loading && !error && events.length" class="events-list">
        <li v-for="event in events" :key="event.event_id" class="event-item" @click="openModal(event)">
          <h2>{{ event.name }}</h2>
          <p><strong>Date:</strong> {{ event.date }} {{ event.time }}</p>
          <p><strong>Place:</strong> {{ event.place }}</p>
          <p><strong>Price:</strong> {{ event.price }}</p>
          <p><strong>Categories:</strong> {{ formatCategories(event.categories) }}</p>
        </li>
      </ul>

      <EventModal
        v-if="modalVisible"
        :event="selectedEvent"
        :visible="modalVisible"
        @close="closeModal"
      />

      <p v-if="!loading && !error && !events.length" class="state">No events found. Go back to subjects.</p>

      <div class="button-wrapper">
        <button @click="$router.push('/subjects')">Back to Subjects</button>
      </div>
    </section>
  </main>
</template>

<script>
import EventModal from "../components/EventModal.vue";

export default {
  name: "EventsPage",
  components: {
    EventModal,
  },
  data() {
    return {
      events: [],
      total: 0,
      loading: true,
      error: "",
      modalVisible: false,
      selectedEvent: null,
    };
  },
  methods: {
    formatCategories(categories) {
    return Array.isArray(categories) && categories.length ? categories.join(", ") : "-";
  },
  async openModal(event) {
    console.log("Opening modal for event", event);
    this.selectedEvent = event;
    this.modalVisible = true;
    try {
      const response = await fetch(`/api/events/${event.event_id || event.id}/`);
      const data = await response.json();
      console.log("Fetched event details", data);
      if (response.ok) {
        this.selectedEvent = data;
      } else {
        this.selectedEvent = { ...event, ai_sentence: 'Nepavyko gauti DI sakinio.' };
      }
    } catch (e) {
      console.log("Fetch error", e);
      this.selectedEvent = { ...event, ai_sentence: 'Nepavyko gauti DI sakinio.' };
    }
  },
  closeModal() {
    this.modalVisible = false;
    this.selectedEvent = null;
  },
},
  async mounted() {
    try {
      const response = await fetch("/api/events/");
      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        throw new Error(data.error || "Failed to load events.");
      }

      this.events = Array.isArray(data.events) ? data.events : [];
      this.total = Number.isInteger(data.total) ? data.total : this.events.length;
    } catch (error) {
      this.error = error.message || "Failed to load events.";
    } finally {
      this.loading = false;
    }
  }
};
</script>

<style scoped>
.page {
  min-height: 100vh;
  display: grid;
  place-items: center;
  background: linear-gradient(135deg, #f3f8ff 0%, #e3f2eb 100%);
  padding: 1rem;
  font-family: "Segoe UI", Tahoma, Geneva, Verdana, sans-serif;
}

.card {
  width: min(720px, 100%);
  background: #ffffff;
  border-radius: 12px;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.08);
  padding: 1.5rem;
  text-align: center;
}

h1 {
  margin: 0 0 0.5rem;
}

.state {
  margin: 0 0 1rem;
  color: #4a5565;
}

.error-message {
  color: #d32f2f;
  font-size: 0.85rem;
  font-weight: 600;
  margin: 0 0 1rem;
  text-align: center;
}

.events-list {
  list-style: none;
  margin: 0 0 1rem;
  padding: 0;
  display: grid;
  gap: 0.75rem;
  text-align: left;
}

.event-item {
  border-radius: 8px;
  border-left: 4px solid #1976d2;
  background: #f8f9fa;
  padding: 0.75rem;
}

.event-item h2 {
  margin: 0 0 0.4rem;
  font-size: 1rem;
}

.event-item p {
  margin: 0.25rem 0;
  color: #4a5565;
}

.button-wrapper {
  display: flex;
  justify-content: center;
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

button:hover {
  background: #115aa0;
}
</style>
