<template>
  <div class="max-w-4xl mx-auto p-6">
    <h2 class="text-2xl font-semibold mb-4">Welcome to Research Paper Mapper</h2>
    <p class="text-gray-700">
      This application allows you to visualize academic research geographically, import papers from Zotero, and perform advanced location-based analysis.
    </p>
    <div class="mt-6 flex space-x-4">
      <router-link to="/map" class="btn btn-primary">Explore Map</router-link>
      <router-link to="/papers" class="btn btn-secondary">View Papers</router-link>
    </div>
  </div>
</template>

<script setup>
// No specific logic currently
</script>
