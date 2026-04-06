<template>
  <div v-if="visible" class="event-modal-overlay">
    <div class="event-modal">
      <button class="close-btn" @click="closeModal">&times;</button>
      <h2>{{ event.name }}</h2>
      <p><strong>Data:</strong> {{ event.date }} {{ event.time }}</p>
      <p><strong>Vieta:</strong> {{ event.place }}</p>
      <p><strong>Kaina:</strong> {{ event.price }}</p>
      <p><strong>Organizatorius:</strong> {{ event.organizer || '-' }}</p>
      <p><strong>Aprašymas:</strong> {{ event.description }}</p>
      <p><strong>Nuoroda:</strong> <a :href="event.source_url" target="_blank">Renginio šaltinis</a></p>
      <p class="ai-sentence"><strong>DI sakinys:</strong> {{ event.ai_sentence }}</p>
      <button class="add-to-calendar-btn" @click="addToGoogleCalendar">Pridėti į Google Calendar</button>
    </div>
  </div>
</template>

<script>
export default {
  name: "EventModal",
  props: {
    event: {
      type: Object,
      required: true,
    },
    visible: {
      type: Boolean,
      required: true,
    },
  },
  data() {
    return {
      tokenClient: null,
      accessToken: null,
    };
  },
  mounted() {
    this.waitForGoogleAuth();
  },
  methods: {
    closeModal() {
      this.$emit("close");
    },
    waitForGoogleAuth() {
      if (window.google && window.google.accounts && window.google.accounts.oauth2) {
        this.initGoogleAuth();
      } else {
        setTimeout(this.waitForGoogleAuth, 100);
      }
    },
    initGoogleAuth() {
      this.tokenClient = window.google.accounts.oauth2.initTokenClient({
        client_id: '979354491672-b0uj6qbsv33as0h5fsquqcaus7f57ckn.apps.googleusercontent.com',
        scope: 'https://www.googleapis.com/auth/calendar.events',
        callback: (response) => {
          if (response.error) {
            console.error('OAuth error:', response);
            alert('Klaida autentifikuojantis su Google.');
          } else {
            this.accessToken = response.access_token;
            this.createCalendarEvent();
          }
        },
      });
    },
    async addToGoogleCalendar() {
      const confirmed = confirm(`Ar tikrai norite pridėti renginį "${this.event.name}" į Google Calendar?`);
      if (!confirmed) return;

      if (!this.tokenClient) {
        alert('Google autentifikacija neinicijuota. Prašome perkrauti puslapį.');
        return;
      }

      this.tokenClient.requestAccessToken();
    },
    async createCalendarEvent() {
      if (!this.accessToken) {
        alert('Nėra prieigos token.');
        return;
      }

      const startDateTime = new Date(`${this.event.date}T${this.event.time}:00`);
      const endDateTime = new Date(startDateTime.getTime() + 60 * 60 * 1000); // Add 1 hour

      const event = {
        summary: this.event.name,
        location: this.event.place,
        description: this.event.description,
        start: {
          dateTime: startDateTime.toISOString(),
          timeZone: 'Europe/Vilnius',
        },
        end: {
          dateTime: endDateTime.toISOString(),
          timeZone: 'Europe/Vilnius',
        },
      };

      try {
        const response = await fetch('https://www.googleapis.com/calendar/v3/calendars/primary/events', {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${this.accessToken}`,
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(event),
        });

        if (response.ok) {
          alert('Renginys pridėtas į Google Calendar!');
        } else {
          const error = await response.json();
          console.error('Error creating event:', error);
          alert('Klaida pridedant renginį į Google Calendar.');
        }
      } catch (error) {
        console.error('Network error:', error);
        alert('Tinklo klaida.');
      }
    },
  },
};
</script>

<style scoped>
.event-modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  background: rgba(0,0,0,0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}
.event-modal {
  background: #fff;
  border-radius: 8px;
  padding: 2rem;
  max-width: 500px;
  width: 100%;
  box-shadow: 0 2px 16px rgba(0,0,0,0.2);
  position: relative;
}
.close-btn {
  position: absolute;
  top: 1rem;
  right: 1rem;
  background: none;
  border: none;
  font-size: 2rem;
  cursor: pointer;
}
.ai-sentence {
  margin-top: 1.5rem;
  font-style: italic;
  color: #2a7a2a;
}
.add-to-calendar-btn {
  position: absolute;
  bottom: 1rem;
  right: 1rem;
  background: #4285f4;
  color: white;
  border: none;
  padding: 0.5rem 1rem;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.9rem;
}
.add-to-calendar-btn:hover {
  background: #3367d6;
}
</style>
