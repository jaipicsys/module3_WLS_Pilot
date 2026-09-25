import { useRouter } from "next/router";
import ProtectedRoute from "../../components/ProtectedRoute";
import Settings from "../../components/Section/Settings/Settings";
import Overview from "../../components/Section/Overview/Overview";
import Report from "../../components/Section/Report/Report";
import Stations from "../../components/Section/Stations/Stations";
import Operators from "../../components/Section/Operators/Operators";
import Sopcompliance from "../../components/Section/Sopcompliance/Sopcompliance";

const SectionPage = () => {
  const router = useRouter();
  const { section } = router.query;

  let Component;
  let allowedRoles = [];

  switch (section) {
    case "overview":
      Component = Overview;
      allowedRoles = [0, 1, 2];
      break;
    case "operator":
      Component = Operators;
      allowedRoles = [0, 1, 2];
      break;
    case "stations":
      Component = Stations;
      allowedRoles = [0, 1, 2];
      break;
    case "sop":
      Component = Sopcompliance;
      allowedRoles = [0, 1, 2];
      break;
    case "reports":
      Component = Report;
      allowedRoles = [0, 1, 2];
      break;
    // case "settings":
    //     Component = Settings;
    //     allowedRoles = [2];
    //     break;
    default:
      return null;
  }

  // return <ProtectedRoute component={Component} roles={allowedRoles} />;
  return <Component />;
};

export default SectionPage;
