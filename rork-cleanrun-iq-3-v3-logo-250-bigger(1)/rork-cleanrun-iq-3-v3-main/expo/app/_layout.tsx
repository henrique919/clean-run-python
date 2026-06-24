import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Stack } from "expo-router";
import * as SplashScreen from "expo-splash-screen";
import { StatusBar } from "expo-status-bar";
import React, { useEffect } from "react";
import { GestureHandlerRootView } from "react-native-gesture-handler";

import { palette } from "@/constants/theme";
import { AppStoreProvider } from "@/providers/AppStore";
import { PlansProvider } from "@/providers/PlansStore";

SplashScreen.preventAutoHideAsync();

const queryClient = new QueryClient();

function RootLayoutNav() {
  return (
    <Stack
      screenOptions={{
        headerBackTitle: "Back",
        headerTintColor: palette.navy,
        headerStyle: { backgroundColor: palette.surface },
        headerTitleStyle: { color: palette.text, fontWeight: "700" },
        contentStyle: { backgroundColor: palette.background },
      }}
    >
      <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
      <Stack.Screen name="item/[id]" options={{ title: "Item", headerBackTitle: "Back" }} />
      <Stack.Screen name="reports" options={{ title: "Reports & Handover" }} />
      <Stack.Screen
        name="report/[type]"
        options={{ title: "Report Preview", presentation: "card" }}
      />
      <Stack.Screen name="subcontractor" options={{ title: "Subcontractor Mode" }} />
      <Stack.Screen name="settings" options={{ title: "Settings & Admin" }} />
      <Stack.Screen name="setup" options={{ title: "Project Setup" }} />
    </Stack>
  );
}

export default function RootLayout() {
  useEffect(() => {
    SplashScreen.hideAsync();
  }, []);

  return (
    <QueryClientProvider client={queryClient}>
      <GestureHandlerRootView style={{ flex: 1 }}>
        <AppStoreProvider>
          <PlansProvider>
            <StatusBar style="dark" />
            <RootLayoutNav />
          </PlansProvider>
        </AppStoreProvider>
      </GestureHandlerRootView>
    </QueryClientProvider>
  );
}
