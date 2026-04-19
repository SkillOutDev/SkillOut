<template>
  <main class="page">
    <section class="card">
      <h1>Events</h1>

      <!-- Filters -->
      <div class="filters">
        <div class="filter-group">
          <label for="city">Miestas:</label>
          <select id="city" v-model="filters.city" @change="applyFilters">
            <option v-for="city in cities" :key="city" :value="city === 'Visi' ? '' : city">{{ city }}</option>
          </select>
        </div>

        <div class="filter-group">
          <label for="minPrice">Kaina nuo:</label>
          <input type="number" id="minPrice" v-model="filters.minPrice" @blur="applyFilters" placeholder="0">
        </div>

        <div class="filter-group">
          <label for="maxPrice">Kaina iki:</label>
          <input type="number" id="maxPrice" v-model="filters.maxPrice" @blur="applyFilters" placeholder="1000">
        </div>

        <div class="filter-group">
          <label for="startDate">Data nuo:</label>
          <input type="date" id="startDate" v-model="filters.startDate" @change="applyFilters">
        </div>

        <div class="filter-group">
          <label for="endDate">Data iki:</label>
          <input type="date" id="endDate" v-model="filters.endDate" @change="applyFilters">
        </div>
      </div>

      <div class="filter-actions">
        <button type="button" class="secondary" @click="clearFilters">Išvalyti filtrus</button>
      </div>

      <p v-if="loading" class="state">Loading events...</p>
      <p v-if="error" class="error-message">{{ error }}</p>
      <p v-if="!loading" class="state">Total: {{ total }}</p>

      <ul v-if="!loading && events.length" class="events-list">
        <li v-for="event in events.filter((item) => String(item?.name || '').trim() && String(item?.date || '').trim())" :key="event.event_id" class="event-item" @click="openModal(event)">
          <h2>{{ event.name }}</h2>
          <p><strong>Date:</strong> {{ event.date }} {{ event.time }}</p>
          <p><strong>Place:</strong> {{ event.place }}</p>
          <p><strong>Price:</strong> {{ formatPrice(event.price) }}</p>
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
      filters: {
        city: "",
        minPrice: "",
        maxPrice: "",
        startDate: "",
        endDate: "",
      },
      cities: ["Visi", "Vilnius", "Kaunas", "Klaipėda", "Šiauliai", "Panevėžys", "Nuotolinis"],
    };
  },
  methods: {
    formatCategories(categories) {
      return Array.isArray(categories) && categories.length ? categories.join(", ") : "-";
    },
    formatPrice(price) {
      if (price === null || price === undefined || String(price).trim() === "") {
        return "-";
      }
      const numericValue = Number(String(price).replace(",", ".").trim());
      if (!Number.isFinite(numericValue)) {
        return "-";
      }

      return `${numericValue.toFixed(2).replace(".", ",")} €`;
    },
    validateFilters() {
      const { minPrice, maxPrice, startDate, endDate } = this.filters;

      if (minPrice !== "" && maxPrice !== "" && Number(minPrice) > Number(maxPrice)) {
        this.error = "Klaida: maksimali kaina negali būti mažesnė už minimalią.";
        this.events = [];
        return false;
      }

      if (startDate && endDate && startDate > endDate) {
        this.error = "Klaida: pabaigos data negali būti ankstesnė už pradžios datą.";
        this.events = [];
        return false;
      }

      this.error = "";
      return true;
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
    async loadEvents() {
      this.loading = true;

      if (!this.validateFilters()) {
        this.loading = false;
        return;
      }

      this.error = "";

      try {
        const hasFilters =
          this.filters.city ||
          this.filters.minPrice ||
          this.filters.maxPrice ||
          this.filters.startDate ||
          this.filters.endDate;

        let url = "/api/events/";
        if (hasFilters) {
          const params = new URLSearchParams();
          if (this.filters.city) params.append("city", this.filters.city);
          if (this.filters.minPrice) params.append("min_price", this.filters.minPrice);
          if (this.filters.maxPrice) params.append("max_price", this.filters.maxPrice);
          if (this.filters.startDate) params.append("start_date", this.filters.startDate);
          if (this.filters.endDate) params.append("end_date", this.filters.endDate);
          url = `/api/events/filter/?${params.toString()}`;
        }

        const response = await fetch(url);
        const data = await response.json().catch(() => ({}));

        if (!response.ok) {
          throw new Error(data.error || "Failed to load events.");
        }

        this.events = Array.isArray(data.events) ? [...data.events] : [];
        this.total = Number.isInteger(data.total) ? data.total : this.events.length;
      } catch (error) {
        this.error = error.message || "Failed to load events.";
      } finally {
        this.loading = false;
      }
    },
    applyFilters() {
      this.loadEvents();
    },
    clearFilters() {
      this.filters = {
        city: "",
        minPrice: "",
        maxPrice: "",
        startDate: "",
        endDate: "",
      };
      this.error = "";
      this.loadEvents();
    },
  },
  async mounted() {
    await this.loadEvents();
  },
};
</script>

<style scoped>
.page {
  min-height: 100vh;
  display: grid;
  place-items: center;
  background: linear-gradient(135deg, #f3f8ff 0%, #e3f2eb 100%);
}

.filters {
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
  margin-bottom: 1rem;
  padding: 1rem;
  background-color: #f9f9f9;
  border-radius: 8px;
}

.filter-group {
  display: flex;
  flex-direction: column;
  min-width: 150px;
}

.filter-group label {
  margin-bottom: 0.5rem;
  font-weight: bold;
}

.filter-group input,
.filter-group select {
  padding: 0.5rem;
  border: 1px solid #ccc;
  border-radius: 4px;
  font-size: 1rem;
}

.filter-actions {
  display: flex;
  justify-content: flex-end;
  width: 100%;
  margin-bottom: 1rem;
}

.card {
  width: min(720px, 100%);
  background: #ffffff;
  border-radius: 12px;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.08);
  padding: 1.5rem;
  text-align: center;
  font-family: "Segoe UI", Tahoma, Geneva, Verdana, sans-serif;
}

button.secondary {
  background: #6b7280;
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
