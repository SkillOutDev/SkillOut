<template>
  <div v-if="visible" class="event-modal-overlay" @click.self.stop="closeModal">
    <div class="event-modal">
      <button class="close-btn" @click="closeModal">&times;</button>
      <h2>{{ event.name }}</h2>
      <p><strong>Data:</strong> {{ event.date }} {{ event.time }}</p>
      <p><strong>Vieta:</strong> {{ event.place }}</p>
      <p><strong>Kaina:</strong> {{ event.price }}</p>
      <p><strong>Organizatorius:</strong> {{ event.organizer || '-' }}</p>
      <p><strong>Aprašymas:</strong> {{ event.short_description }}</p>
      <p><strong>Nuoroda:</strong> <a :href="event.source_url" target="_blank">Renginio šaltinis</a></p>
      <p class="ai-sentence"><strong>DI sakinys:</strong> {{ event.ai_sentence }}</p>
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
  methods: {
    closeModal() {
      this.$emit("close");
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
</style>
