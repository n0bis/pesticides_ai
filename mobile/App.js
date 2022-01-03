import { StatusBar } from "expo-status-bar";
import React, { useEffect } from "react";
import MapView, { Marker } from "react-native-maps";
import { StyleSheet, Text, View, Dimensions } from "react-native";
import { createMaterialBottomTabNavigator } from "@react-navigation/material-bottom-tabs";
import { NavigationContainer } from "@react-navigation/native";
import * as Location from "expo-location";

const Tab = createMaterialBottomTabNavigator();

function HomeScreen() {
  return (
    <View style={styles.container}>
      <Text>Semester Project in Scalable Systems</Text>
    </View>
  );
}

function SettingsScreen() {
  useEffect(() => {
    (async () => {
      let { status } = await Location.requestForegroundPermissionsAsync();
      if (status !== "granted") {
        //setErrorMsg("Permission to access location was denied");
        return;
      }

      let location = await Location.getCurrentPositionAsync({});
      setLocation(location);
    })();
  }, []);

  return (
    <View style={styles.container}>
      <MapView
        style={styles.map}
        coordinate={{
          latitude: 55.475664,
          longitude: 9.092876,
          latitudeDelta: 0.0,
          longitudeDelta: 0.0,
        }}
        showsUserLocation
        mapType="satellite"
      >
        <Marker
          title="Field 1"
          description="This field is sprayed with pesticides"
          coordinate={{
            latitude: 55.38095915335372,
            longitude: 10.482410924642748,
            latitudeDelta: 0.0,
            longitudeDelta: 0.0,
          }}
        />
        <Marker
          title="Field 2"
          description="This field is NOT sprayed with pesticides"
          coordinate={{
            latitude: 55.35154614509212,
            longitude: 10.447234064998021,
            latitudeDelta: 0.0,
            longitudeDelta: 0.0,
          }}
        />
      </MapView>
    </View>
  );
}

function MyTabs() {
  return (
    <NavigationContainer>
      <Tab.Navigator>
        <Tab.Screen name="About" component={HomeScreen} />
        <Tab.Screen name="Map view" component={SettingsScreen} />
      </Tab.Navigator>
    </NavigationContainer>
  );
}

export default function App() {
  return <MyTabs />;
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#fff",
    alignItems: "center",
    justifyContent: "center",
  },
  map: {
    width: Dimensions.get("window").width,
    height: Dimensions.get("window").height,
  },
});
