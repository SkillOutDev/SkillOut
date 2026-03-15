import { createRouter, createWebHistory } from "vue-router";
import UrlFormPage from "../pages/UrlFormPage.vue";
import SubjectsPage from "../pages/SubjectsPage.vue";

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
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

export default router;
