import { createRouter, createWebHistory } from "vue-router";
import UrlFormPage from "../pages/UrlFormPage.vue";
import SubjectsPage from "../pages/SubjectsPage.vue";
import EventsPage from "../pages/EventsPage.vue";

const routes = [
  {
    path: "/",
    name: "url-form",
    component: UrlFormPage,
  },
  {
    path: "/subjects",
    name: "subjects",
    component: SubjectsPage,
  },
  {
    path: "/events",
    name: "events",
    component: EventsPage,
  },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

export default router;
