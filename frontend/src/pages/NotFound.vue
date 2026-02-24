<template>
  <v-container class="fill-height" fluid>
    <v-row align="center" justify="center">
      <v-col cols="12" class="text-center">
        <h2 class="text-h1 font-weight-bold mb-4">404</h2>
        <p class="text-h6 text-medium-emphasis mb-6">Page not found</p>
        <v-btn color="primary" to="/" prepend-icon="mdi-home">Go Home</v-btn>
      </v-col>
    </v-row>
  </v-container>
</template>

<script setup></script>

<style scoped>
.fill-height {
  min-height: 60vh;
}
</style>
