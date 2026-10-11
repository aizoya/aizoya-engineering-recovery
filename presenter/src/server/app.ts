import { startApp } from 'modelence/server';
import missionModule from './mission/module';

startApp({
  modules: [missionModule],
  migrations: [],
});
