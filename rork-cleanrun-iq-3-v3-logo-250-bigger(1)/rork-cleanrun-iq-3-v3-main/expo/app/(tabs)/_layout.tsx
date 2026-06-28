import { Tabs } from "expo-router";
import { ClipboardList, Home, Map, MoreHorizontal, Plus } from "lucide-react-native";
import React from "react";
import { Platform, StyleSheet, View } from "react-native";

import { palette, shadow } from "@/constants/theme";

export default function TabLayout() {
  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: palette.navy,
        tabBarInactiveTintColor: palette.textFaint,
        tabBarStyle: {
          backgroundColor: palette.surface,
          borderTopColor: palette.border,
          height: Platform.OS === "ios" ? 88 : 64,
          paddingTop: 6,
        },
        tabBarLabelStyle: { fontSize: 11, fontWeight: "600" },
      }}
    >
      <Tabs.Screen
        name="index"
        options={{ title: "Home", tabBarIcon: ({ color, size }) => <Home color={color} size={size} /> }}
      />
      <Tabs.Screen
        name="items"
        options={{
          title: "Items",
          tabBarIcon: ({ color, size }) => <ClipboardList color={color} size={size} />,
        }}
      />
      <Tabs.Screen
        name="capture"
        options={{
          title: "Capture",
          tabBarIcon: () => (
            <View style={styles.captureButton}>
              <Plus color={palette.white} size={26} strokeWidth={2.6} />
            </View>
          ),
          tabBarLabelStyle: { fontSize: 11, fontWeight: "700", color: palette.navy },
        }}
      />
      <Tabs.Screen
        name="plans"
        options={{ title: "Plans", tabBarIcon: ({ color, size }) => <Map color={color} size={size} /> }}
      />
      <Tabs.Screen
        name="more"
        options={{
          title: "More",
          tabBarIcon: ({ color, size }) => <MoreHorizontal color={color} size={size} />,
        }}
      />
    </Tabs>
  );
}

const styles = StyleSheet.create({
  captureButton: {
    width: 54,
    height: 54,
    borderRadius: 27,
    backgroundColor: palette.navy,
    alignItems: "center",
    justifyContent: "center",
    marginTop: -18,
    borderWidth: 4,
    borderColor: palette.surface,
    ...shadow.floating,
  },
});
